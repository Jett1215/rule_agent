from agentruler.services.storage.oss import OSSClient
from agentruler.services.storage.minio import MinioClient
from agentruler.settings import app_settings

if app_settings.storage.mode == "minio":
    storage_client = MinioClient()
else:
    storage_client = OSSClient()

if __name__ == "__main__":
    storage_client.list_files_in_folder("icons/user/")