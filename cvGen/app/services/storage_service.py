from __future__ import annotations
from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from app.core.config import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_S3_BUCKET_NAME, AWS_S3_PREFIX, AWS_SECRET_ACCESS_KEY

logger = logging.getLogger(__name__)


class StorageProvider(Protocol):
    provider_name: str

    def upload_or_replace_pdf(self, *, student_id: str, pdf_bytes: bytes, display_name: str) -> str:
        ...

    def download_pdf(self, *, object_id: str) -> BytesIO:
        ...


class StorageProviderError(Exception):
    pass


class S3Error(StorageProviderError):
    pass


@dataclass
class S3StorageProvider:
    bucket_name: str
    prefix: str = "cvs"
    region: str = "us-east-1"
    provider_name: str = "s3"

    def __post_init__(self) -> None:
        if not self.bucket_name:
            raise S3Error("AWS_S3_BUCKET_NAME is required for S3 storage")

        session_kwargs: dict[str, str] = {"region_name": self.region}
        if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            session_kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
            session_kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

        try:
            self._client = boto3.client("s3", **session_kwargs)
            self._client.head_bucket(Bucket=self.bucket_name)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise S3Error(f"Cannot access S3 bucket '{self.bucket_name}': {error_code}") from exc

    def _object_key(self, student_id: str) -> str:
        clean_prefix = self.prefix.strip("/")
        file_name = f"{student_id}.pdf"
        return f"{clean_prefix}/{file_name}" if clean_prefix else file_name

    def upload_or_replace_pdf(self, *, student_id: str, pdf_bytes: bytes, display_name: str) -> str:
        key = self._object_key(student_id)

        try:
            self._client.head_object(Bucket=self.bucket_name, Key=key)
            self._client.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
                logger.warning("[S3_STORAGE] Existing object check failed for %s: %s", key, exc)

        try:
            self._client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=pdf_bytes,
                ContentType="application/pdf",
                Metadata={"display_name": display_name, "student_id": student_id},
            )
            return key
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            raise S3Error(f"S3 upload failed: [{error_code}] {error_msg}") from exc
        except Exception as exc:
            raise S3Error(f"Unexpected error during S3 upload: {exc}") from exc

    def download_pdf(self, *, object_id: str) -> BytesIO:
        try:
            obj = self._client.get_object(Bucket=self.bucket_name, Key=object_id)
            stream = BytesIO(obj["Body"].read())
            stream.seek(0)
            return stream
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                raise S3Error(f"S3 object not found: {object_id}") from exc
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            raise S3Error(f"S3 download failed: [{error_code}] {error_msg}") from exc
        except Exception as exc:
            raise S3Error(f"Unexpected error during S3 download: {exc}") from exc


def get_storage_provider(provider: str | None = None) -> StorageProvider:
    selected = (provider or "s3").strip().lower()
    if selected not in {"s3", "aws", "amazon_s3"}:
        raise StorageProviderError("Only the S3 storage provider is supported")

    return S3StorageProvider(bucket_name=AWS_S3_BUCKET_NAME, prefix=AWS_S3_PREFIX, region=AWS_REGION)
