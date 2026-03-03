import enum

import boto3
from botocore.exceptions import ClientError
from structlog import get_logger

log = get_logger(__name__)


class CloudRequest(enum.Enum):
    Download = "get_object"
    Upload = "put_object"


class IDriveClient:
    def __init__(self, endpoint: str, access_key: str, secret_access_key: str):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_access_key = secret_access_key
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_access_key,
        )

    def create_presigned_url(
        self,
        bucket_name: str,
        file_path: str,
        expiration: int = 3600,
        request_type: CloudRequest = CloudRequest.Download,
        content_type=None,
    ):
        try:
            params = {"Bucket": bucket_name, "Key": file_path}
            if content_type:
                params["ContentType"] = content_type

            response = self.client.generate_presigned_url(
                request_type.value, Params=params, ExpiresIn=expiration
            )
        except ClientError as e:
            print(e)
            return None
        return response

    def upload_file(self, file: bytes, file_path: str, bucket_name: str):
        try:
            self.client.upload_fileobj(file, bucket_name, file_path)
        except ClientError as e:
            print(e)
            return False
        return True

    def delete_file(self, file_path: str, bucket_name: str):
        try:
            self.client.delete_object(Bucket=bucket_name, Key=file_path)
        except ClientError:
            log.warning(
                "Deletion on s3 client failed",
                client=self.__class__,
                bucket_name=bucket_name,
                file_path=file_path,
            )
