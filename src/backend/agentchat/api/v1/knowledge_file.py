import os
import asyncio
import json
from typing import Literal
from urllib.parse import quote
from urllib.parse import urlparse
from fastapi import APIRouter, Body, Depends, Query, HTTPException, Response

from agentchat.services.storage import storage_client
from agentchat.api.services.knowledge_file import KnowledgeFileService
from agentchat.api.services.knowledge import KnowledgeService
from agentchat.api.services.user import get_login_user, UserPayload
from agentchat.api.responses.builder import UnifiedResponseModel, resp_200, resp_500
from agentchat.utils.file_utils import get_save_tempfile

router = APIRouter(tags=["Knowledge-File"])


async def get_authorized_chunk_file(file_id, login_user):
    from agentchat.database.models.user import AdminUser

    file = await KnowledgeFileService.select_knowledge_file_by_id(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if login_user.user_id not in (AdminUser, file.user_id):
        raise HTTPException(status_code=403, detail="没有权限访问该文件")
    try:
        await KnowledgeService.verify_user_permission(file.knowledge_id, login_user.user_id)
    except ValueError:
        raise HTTPException(status_code=403, detail="没有权限访问该知识库")
    return file


def get_chunk_browser_client():
    from agentchat.settings import app_settings
    if app_settings.rag.vector_db.get("mode") != "chroma":
        raise HTTPException(status_code=400, detail="当前 Chunk 查看功能仅支持 ChromaDB")
    from agentchat.services.rag.vector_stores import milvus_client
    return milvus_client.client


@router.get('/knowledge_file/chunks', response_model=UnifiedResponseModel)
async def list_file_chunks(
    knowledge_file_id: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    search: str = Query("", max_length=200),
    login_user: UserPayload = Depends(get_login_user)
):
    from agentchat.services.rag.chunk_browser import browse_file_chunks
    file = await get_authorized_chunk_file(knowledge_file_id, login_user)
    result = await asyncio.to_thread(browse_file_chunks, get_chunk_browser_client(),
                                    file.knowledge_id, file.id, page, page_size, search.strip())
    return resp_200(data=result)


@router.get('/knowledge_file/chunks/vector', response_model=UnifiedResponseModel)
async def read_chunk_vector(
    knowledge_file_id: str = Query(...),
    record_id: str = Query(...),
    login_user: UserPayload = Depends(get_login_user)
):
    from agentchat.services.rag.chunk_browser import get_chunk_vector
    file = await get_authorized_chunk_file(knowledge_file_id, login_user)
    result = await asyncio.to_thread(get_chunk_vector, get_chunk_browser_client(),
                                    file.knowledge_id, file.id, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Chunk 不存在")
    return resp_200(data=result)


@router.get('/knowledge_file/chunks/export')
async def download_file_chunks(
    knowledge_file_id: str = Query(...),
    format: Literal["txt", "json"] = Query("txt"),
    login_user: UserPayload = Depends(get_login_user)
):
    from agentchat.services.rag.chunk_browser import export_file_chunks
    file = await get_authorized_chunk_file(knowledge_file_id, login_user)
    items = await asyncio.to_thread(export_file_chunks, get_chunk_browser_client(), file.knowledge_id, file.id)
    if format == "json":
        text = json.dumps({"file_name": file.file_name, "knowledge_id": file.knowledge_id,
                           "file_id": file.id, "items": items}, ensure_ascii=False, indent=2)
        media_type = "application/json"
    else:
        parts = [f"文件：{file.file_name}\n知识库：{file.knowledge_id}\n记录数：{len(items)}"]
        for number, item in enumerate(items, 1):
            kind = "摘要" if item["metadata"].get("is_summary") else "正文"
            parts.append(f"\n{'=' * 60}\n记录 {number}（{kind}）\nID：{item['id']}\n"
                         f"字符数：{len(item['content'])}\n向量维度：{len(item['embedding'])}\n"
                         f"元信息：{json.dumps(item['metadata'], ensure_ascii=False)}\n\n{item['content']}")
        text = "\ufeff" + "\n".join(parts)
        media_type = "text/plain"
    filename = quote(f"{file.file_name}_chunks.{format}", safe="")
    return Response(content=text, media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})


@router.post('/knowledge_file/create', response_model=UnifiedResponseModel)
async def upload_file(
    knowledge_id: str = Body(..., description="知识库的ID"),
    file_url: str = Body(..., description="文件上传后返回的URL"),
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        # 获取本地临时文件路径
        file_name = file_url.split("/")[-1]
        local_file_path = get_save_tempfile(file_name)
        # 根据URL解析出对应的object name
        parsed = urlparse(file_url)
        object_key = parsed.path.lstrip('/')
        storage_client.download_file(object_key, local_file_path)
        # 获得文件的字节数
        file_size_bytes = os.path.getsize(local_file_path)

        name_part, ext_part = file_name.rsplit('.', 1) if '.' in file_name else (file_name, '')
        parts = name_part.split("_")
        file_name = "_".join(parts[:-1]) + f".{ext_part}"

        await KnowledgeFileService.create_knowledge_file(
            file_name=file_name,
            file_path=local_file_path,
            knowledge_id=knowledge_id,
            user_id=login_user.user_id,
            oss_url=file_url,
            file_size_bytes=file_size_bytes
        )
        return resp_200()
    except Exception as err:
        return resp_500(message=str(err))

@router.get('/knowledge_file/select', response_model=UnifiedResponseModel)
async def select_knowledge_file(
    knowledge_id: str = Query(...),
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        # 验证用户权限
        await KnowledgeService.verify_user_permission(knowledge_id, login_user.user_id)

        results = await KnowledgeFileService.get_knowledge_file(knowledge_id)
        return resp_200(data=results)
    except Exception as err:
        return resp_500(message=str(err))


@router.delete('/knowledge_file/delete', response_model=UnifiedResponseModel)
async def delete_knowledge_file(
    knowledge_file_id: str = Body(..., embed=True),
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        # 验证用户权限
        await KnowledgeFileService.verify_user_permission(knowledge_file_id, login_user.user_id)

        await KnowledgeFileService.delete_knowledge_file(knowledge_file_id)
        return resp_200()
    except Exception as err:
        return resp_500(message=str(err))

@router.get("/knowledge_file/status", response_model=UnifiedResponseModel)
async def get_knowledge_file_status(
    knowledge_file_id: str = Body(..., embed=True),
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        # 验证用户权限
        await KnowledgeFileService.verify_user_permission(knowledge_file_id, login_user.user_id)
        knowledge_file = await KnowledgeFileService.select_knowledge_file_by_id(knowledge_file_id)
        return resp_200(data=knowledge_file.to_dict())
    except Exception as err:
        return resp_500(message=str(err))
