from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

import boto3
from botocore.exceptions import ClientError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError

from app.core.config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_S3_BUCKET_NAME,
    AWS_S3_PREFIX,
    AWS_SECRET_ACCESS_KEY,
    DEFAULT_STORAGE_PROVIDER,
    PARENT_FOLDER_ID,
)
from app.services.google_auth import get_drive_service

logger = logging.getLogger(__name__)


class StorageProvider(Protocol):
    """Protocol for storage provider implementations."""
    provider_name: str

    def upload_or_replace_pdf(self, *, student_id: str, pdf_bytes: bytes, display_name: str) -> str:
        ...

    def download_pdf(self, *, object_id: str) -> BytesIO:
        ...

class StorageProviderError(Exception):
    """Base exception for storage provider errors."""
    pass


class S3Error(StorageProviderError):
    """S3-specific storage errors."""
    pass


class GoogleDriveError(StorageProviderError):
    """Google Drive-specific storage errors."""
    pass




@dataclass
class S3StorageProvider:
    bucket_name: str
    prefix: str = "cvs"
    region: str = "us-east-1"
    provider_name: str = "s3"

    def __post_init__(self) -> None:
        if not self.bucket_name:
            logger.error("[S3_STORAGE] AWS_S3_BUCKET_NAME is not configured")
            raise S3Error("AWS_S3_BUCKET_NAME is required for S3 storage")

        try:
            logger.debug("[S3_STORAGE] Initializing S3 client for bucket: %s, region: %s", self.bucket_name, self.region)
            session_kwargs = {"region_name": self.region}
            if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                session_kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
                session_kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
                logger.debug("[S3_STORAGE] Using explicit AWS credentials")
            else:
                logger.debug("[S3_STORAGE] Using default AWS credentials chain (IAM roles, env vars, etc.)")

            self._client = boto3.client("s3", **session_kwargs)
            logger.info("[S3_STORAGE] S3 client initialized successfully")
            
            # Validate bucket access
            try:
                self._client.head_bucket(Bucket=self.bucket_name)
                logger.info("[S3_STORAGE] S3 bucket access validated: %s", self.bucket_name)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "Unknown")
                logger.error("[S3_STORAGE] Cannot access S3 bucket %s: %s", self.bucket_name, error_code)
                raise S3Error(f"Cannot access S3 bucket '{self.bucket_name}': {error_code}") from exc
                
        except Exception as exc:
            logger.error("[S3_STORAGE] Failed to initialize S3 provider: %s\n%s", exc, traceback.format_exc())
            raise

    def _object_key(self, student_id: str) -> str:
        clean_prefix = self.prefix.strip("/")
        if clean_prefix:
            return f"{clean_prefix}/{student_id}.pdf"
        return f"{student_id}.pdf"

    def upload_or_replace_pdf(self, *, student_id: str, pdf_bytes: bytes, display_name: str) -> str:
        """Upload or replace PDF in S3 with idempotency (one file per student)."""
        key = self._object_key(student_id)
        
        try:
            logger.info("[S3_STORAGE] Starting upload for student %s to key: %s", student_id, key)
            
            # Step 1: Delete existing object (idempotent - doesn't fail if not found)
            try:
                logger.debug("[S3_STORAGE] Checking for existing object to delete: %s", key)
                self._client.head_object(Bucket=self.bucket_name, Key=key)
                logger.info("[S3_STORAGE] Found existing object, deleting: %s", key)
                self._client.delete_object(Bucket=self.bucket_name, Key=key)
                logger.info("[S3_STORAGE] Deleted existing object: %s", key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "404":
                    logger.debug("[S3_STORAGE] No existing object found (expected): %s", key)
                else:
                    logger.warning("[S3_STORAGE] Could not check for existing object: %s", exc)
            
            # Step 2: Upload new object
            logger.debug("[S3_STORAGE] Uploading new PDF (%d bytes) for student %s", len(pdf_bytes), student_id)
            self._client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=pdf_bytes,
                ContentType="application/pdf",
                Metadata={"display_name": display_name, "student_id": student_id},
            )
            logger.info("[S3_STORAGE] Successfully uploaded PDF for student %s (size: %d bytes, key: %s)", student_id, len(pdf_bytes), key)
            return key
            
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            logger.error("[S3_STORAGE] S3 upload failed for student %s (key: %s): [%s] %s\n%s", student_id, key, error_code, error_msg, traceback.format_exc())
            raise S3Error(f"S3 upload failed: [{error_code}] {error_msg}") from exc
        except Exception as exc:
            logger.error("[S3_STORAGE] Unexpected error uploading to S3 for student %s: %s\n%s", student_id, exc, traceback.format_exc())
            raise S3Error(f"Unexpected error during S3 upload: {exc}") from exc

    def download_pdf(self, *, object_id: str) -> BytesIO:
        """Download PDF from S3."""
        try:
            logger.info("[S3_STORAGE] Starting download for object_id: %s", object_id)
            obj = self._client.get_object(Bucket=self.bucket_name, Key=object_id)
            logger.debug("[S3_STORAGE] Retrieved object metadata, reading body...")
            
            stream = BytesIO(obj["Body"].read())
            stream.seek(0)
            logger.info("[S3_STORAGE] Successfully downloaded PDF from S3 (size: %d bytes, key: %s)", len(stream.getvalue()), object_id)
            return stream
            
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.warning("[S3_STORAGE] S3 object not found: %s", object_id)
                raise S3Error(f"S3 object not found: {object_id}") from exc
            else:
                error_msg = exc.response.get("Error", {}).get("Message", str(exc))
                logger.error("[S3_STORAGE] S3 download error for %s: [%s] %s\n%s", object_id, error_code, error_msg, traceback.format_exc())
                raise S3Error(f"S3 download failed: [{error_code}] {error_msg}") from exc
        except Exception as exc:
            logger.error("[S3_STORAGE] Unexpected error downloading from S3 (object_id: %s): %s\n%s", object_id, exc, traceback.format_exc())
            raise S3Error(f"Unexpected error during S3 download: {exc}") from exc


@dataclass
class GoogleDriveStorageProvider:
    parent_folder_id: str
    provider_name: str = "google_drive"

    def __post_init__(self) -> None:
        if not self.parent_folder_id:
            logger.error("[GDRIVE_STORAGE] GOOGLE_DRIVE_FOLDER_ID is not configured")
            raise GoogleDriveError("GOOGLE_DRIVE_FOLDER_ID is required for Google Drive storage")
        
        try:
            logger.info("[GDRIVE_STORAGE] Initializing Google Drive service for folder: %s", self.parent_folder_id)
            self._service = get_drive_service()
            logger.info("[GDRIVE_STORAGE] Google Drive service initialized successfully")
        except Exception as exc:
            logger.error("[GDRIVE_STORAGE] Failed to initialize Google Drive service: %s\n%s", exc, traceback.format_exc())
            raise GoogleDriveError(f"Failed to initialize Google Drive service: {exc}") from exc

    def _query_by_student_id(self, student_id: str) -> str:
        file_name = f"{student_id}.pdf"
        return f"name = '{file_name}' and '{self.parent_folder_id}' in parents and trashed = false"

    def upload_or_replace_pdf(self, *, student_id: str, pdf_bytes: bytes, display_name: str) -> str:
        """Upload or replace PDF in Google Drive with idempotency."""
        file_name = f"{student_id}.pdf"
        
        try:
            logger.info("[GDRIVE_STORAGE] Starting upload for student %s", student_id)
            query = self._query_by_student_id(student_id)
            
            # Step 1: Find and delete existing files
            try:
                logger.debug("[GDRIVE_STORAGE] Searching for existing files with query: %s", query)
                results = self._service.files().list(q=query, fields="files(id, name)").execute()
                existing_files = results.get("files", [])
                
                if existing_files:
                    logger.info("[GDRIVE_STORAGE] Found %d existing file(s) for student %s", len(existing_files), student_id)
                    for item in existing_files:
                        try:
                            logger.debug("[GDRIVE_STORAGE] Deleting file: %s (ID: %s)", item["name"], item["id"])
                            self._service.files().delete(fileId=item["id"]).execute()
                            logger.info("[GDRIVE_STORAGE] Deleted file: %s", item["id"])
                        except Exception as exc:
                            logger.warning("[GDRIVE_STORAGE] Failed to delete existing file %s: %s", item["id"], exc)
                else:
                    logger.debug("[GDRIVE_STORAGE] No existing files found for student %s (expected)", student_id)
                    
            except Exception as exc:
                logger.warning("[GDRIVE_STORAGE] Error checking for existing files: %s", exc)
            
            # Step 2: Upload new file
            try:
                logger.debug("[GDRIVE_STORAGE] Uploading new PDF (%d bytes) for student %s", len(pdf_bytes), student_id)
                media = MediaIoBaseUpload(BytesIO(pdf_bytes), mimetype="application/pdf", resumable=True)
                body = {
                    "name": file_name,
                    "mimeType": "application/pdf",
                    "parents": [self.parent_folder_id],
                    "description": f"CV for {display_name}",
                }
                created = self._service.files().create(body=body, media_body=media, fields="id").execute()
                file_id = created["id"]
                logger.info("[GDRIVE_STORAGE] Successfully uploaded PDF for student %s (File ID: %s, size: %d bytes)", student_id, file_id, len(pdf_bytes))
                return file_id
                
            except Exception as exc:
                logger.error("[GDRIVE_STORAGE] Failed to upload PDF to Google Drive: %s\n%s", exc, traceback.format_exc())
                raise GoogleDriveError(f"Failed to upload PDF to Google Drive: {exc}") from exc
                
        except GoogleDriveError:
            raise
        except Exception as exc:
            logger.error("[GDRIVE_STORAGE] Unexpected error during Google Drive upload for student %s: %s\n%s", student_id, exc, traceback.format_exc())
            raise GoogleDriveError(f"Unexpected error during Google Drive upload: {exc}") from exc

    def download_pdf(self, *, object_id: str) -> BytesIO:
        """Download PDF from Google Drive."""
        try:
            logger.info("[GDRIVE_STORAGE] Starting download for file ID: %s", object_id)
            
            request = self._service.files().get_media(fileId=object_id)
            file_stream = BytesIO()
            downloader = MediaIoBaseDownload(file_stream, request)

            logger.debug("[GDRIVE_STORAGE] Downloading file in chunks...")
            done = False
            chunk_count = 0
            while done is False:
                _, done = downloader.next_chunk()
                chunk_count += 1
            
            file_stream.seek(0)
            logger.info("[GDRIVE_STORAGE] Successfully downloaded PDF from Google Drive (File ID: %s, chunks: %d, size: %d bytes)", object_id, chunk_count, len(file_stream.getvalue()))
            return file_stream
            
        except HttpError as exc:
            error_code = exc.resp.status
            logger.error("[GDRIVE_STORAGE] Google Drive HTTP error for file %s: [%d] %s\n%s", object_id, error_code, exc, traceback.format_exc())
            raise GoogleDriveError(f"Google Drive error (HTTP {error_code}): {exc}") from exc
        except Exception as exc:
            logger.error("[GDRIVE_STORAGE] Unexpected error downloading from Google Drive (file ID: %s): %s\n%s", object_id, exc, traceback.format_exc())
            raise GoogleDriveError(f"Unexpected error during Google Drive download: {exc}") from exc


def get_storage_provider(provider: str | None = None) -> StorageProvider:
    """Factory function to get the appropriate storage provider."""
    selected = (provider or DEFAULT_STORAGE_PROVIDER or "s3").strip().lower()
    
    logger.info("[STORAGE] Initializing storage provider: %s (requested: %s, default: %s)", selected, provider, DEFAULT_STORAGE_PROVIDER)

    if selected in {"s3", "aws", "amazon_s3"}:
        try:
            logger.debug("[STORAGE] Creating S3StorageProvider")
            return S3StorageProvider(
                bucket_name=AWS_S3_BUCKET_NAME,
                prefix=AWS_S3_PREFIX,
                region=AWS_REGION,
            )
        except Exception as exc:
            logger.error("[STORAGE] Failed to create S3StorageProvider: %s\n%s", exc, traceback.format_exc())
            raise

    if selected in {"google_drive", "gdrive", "drive"}:
        try:
            logger.debug("[STORAGE] Creating GoogleDriveStorageProvider")
            return GoogleDriveStorageProvider(parent_folder_id=PARENT_FOLDER_ID)
        except Exception as exc:
            logger.error("[STORAGE] Failed to create GoogleDriveStorageProvider: %s\n%s", exc, traceback.format_exc())
            raise

    logger.error("[STORAGE] Unsupported storage provider requested: %s", selected)
    raise StorageProviderError(f"Unsupported storage provider: {selected}. Supported: s3, google_drive")
