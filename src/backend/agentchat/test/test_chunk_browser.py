import tempfile
import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import chromadb

from agentchat.services.rag.chunk_browser import browse_file_chunks, export_file_chunks, get_chunk_vector


class ChunkBrowserTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.client = chromadb.PersistentClient(path=self.directory.name)
        collection = self.client.create_collection("test-knowledge", embedding_function=None)
        collection.add(
            ids=["body-1", "body-2", "body-1_summary", "other-file"],
            documents=["第一段证券知识", "第二段考试要求", "证券知识摘要", "不应泄露的其他文件"],
            embeddings=[[1., 0., 0.], [0., 1., 0.], [0., 0., 1.], [1., 1., 0.]],
            metadatas=[
                {"file_id": "file-1", "is_summary": False, "summary": "证券知识摘要"},
                {"file_id": "file-1", "is_summary": False},
                {"file_id": "file-1", "is_summary": True, "chunk_id": "body-1"},
                {"file_id": "file-2", "is_summary": False},
            ],
        )

    def test_pagination_and_counts_are_scoped_to_file(self):
        first = browse_file_chunks(self.client, "test-knowledge", "file-1", page_size=2)
        second = browse_file_chunks(self.client, "test-knowledge", "file-1", page=2, page_size=2)
        self.assertEqual(first["total"], 3)
        self.assertEqual((first["content_count"], first["summary_count"]), (2, 1))
        self.assertEqual((len(first["items"]), len(second["items"])), (2, 1))
        ids = {item["id"] for item in first["items"] + second["items"]}
        self.assertEqual(ids, {"body-1", "body-2", "body-1_summary"})
        self.assertEqual(first["items"][0]["vector_dimension"], 3)

    def test_search_matches_body_and_summary_with_accurate_total(self):
        result = browse_file_chunks(self.client, "test-knowledge", "file-1", search="证券")
        self.assertEqual(result["total"], 2)
        self.assertEqual({item["id"] for item in result["items"]}, {"body-1", "body-1_summary"})
        self.assertEqual(browse_file_chunks(self.client, "test-knowledge", "file-1", search="不存在")["total"], 0)

    def test_vector_cannot_be_read_from_another_file(self):
        vector = get_chunk_vector(self.client, "test-knowledge", "file-1", "body-1")
        self.assertEqual(vector["embedding"], [1., 0., 0.])
        self.assertIsNone(get_chunk_vector(self.client, "test-knowledge", "file-1", "other-file"))

    def test_export_includes_all_records_and_full_vectors_for_only_one_file(self):
        records = export_file_chunks(self.client, "test-knowledge", "file-1")
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["metadata"]["file_id"] == "file-1" for record in records))
        self.assertTrue(all(len(record["embedding"]) == 3 for record in records))

    def test_missing_collection_or_file_returns_empty_results(self):
        self.assertEqual(browse_file_chunks(self.client, "missing-knowledge", "file-1")["items"], [])
        self.assertEqual(browse_file_chunks(self.client, "test-knowledge", "missing-file")["total"], 0)
        self.assertEqual(export_file_chunks(self.client, "missing-knowledge", "file-1"), [])
        self.assertIsNone(get_chunk_vector(self.client, "missing-knowledge", "file-1", "body-1"))

    def api_client(self, file_owner="owner", missing=False):
        from agentchat.settings import init_app_settings
        asyncio.run(init_app_settings())
        from agentchat.api.v1 import knowledge_file as api
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(api.router)
        app.dependency_overrides[api.get_login_user] = lambda: SimpleNamespace(user_id="owner")
        file = None if missing else SimpleNamespace(
            id="file-1", knowledge_id="test-knowledge", file_name="证券测试.txt", user_id=file_owner)
        patches = [
            patch.object(api.KnowledgeFileService, "select_knowledge_file_by_id", AsyncMock(return_value=file)),
            patch.object(api.KnowledgeService, "verify_user_permission", AsyncMock()),
            patch.object(api, "get_chunk_browser_client", return_value=self.client),
        ]
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def test_api_serializes_page_and_exports_txt_and_json(self):
        client = self.api_client()
        response = client.get("/knowledge_file/chunks", params={"knowledge_file_id": "file-1", "page_size": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["items"]), 2)
        for format in ["txt", "json"]:
            response = client.get("/knowledge_file/chunks/export", params={"knowledge_file_id": "file-1", "format": format})
            self.assertEqual(response.status_code, 200)
            self.assertIn("filename*=UTF-8''", response.headers["content-disposition"])
            if format == "json":
                self.assertEqual(len(response.json()["items"]), 3)
            else:
                self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
                self.assertIn("第一段证券知识", response.text)
        self.assertEqual(client.get("/knowledge_file/chunks", params={"knowledge_file_id": "file-1", "page_size": 100}).status_code, 422)

    def test_api_denies_other_users_for_list_vector_and_export(self):
        client = self.api_client(file_owner="another-owner")
        for endpoint in ["chunks", "chunks/vector", "chunks/export"]:
            response = client.get(f"/knowledge_file/{endpoint}", params={"knowledge_file_id": "file-1", "record_id": "body-1"})
            self.assertEqual(response.status_code, 403)

    def test_api_missing_file_returns_404(self):
        client = self.api_client(missing=True)
        self.assertEqual(client.get("/knowledge_file/chunks", params={"knowledge_file_id": "file-1"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
