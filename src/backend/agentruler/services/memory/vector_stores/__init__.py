from agentruler.settings import app_settings
from agentruler.services.memory.vector_stores.chroma import ChromaDB

class VectorStoreManager:

    @classmethod
    def get_chroma_vector(cls):
        return ChromaDB(
            collection_name=app_settings.default_config.get("memory_collection_name")
        )

    @classmethod
    def get_milvus_vector(cls):
        pass