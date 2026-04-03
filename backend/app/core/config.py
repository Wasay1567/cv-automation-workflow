import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

# Google Drive configuration
PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Service account credentials path
# This should point to your GCP service account JSON key file
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Storage provider configuration
DEFAULT_STORAGE_PROVIDER = os.getenv("DEFAULT_STORAGE_PROVIDER", "s3").strip().lower()

# AWS S3 configuration
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_S3_PREFIX = os.getenv("AWS_S3_PREFIX", "cvs")

logger.info("[CONFIG] LOG_LEVEL: %s", LOG_LEVEL)
logger.info("[CONFIG] PARENT_FOLDER_ID: %s", "***" if PARENT_FOLDER_ID else "NOT_SET")
logger.info("[CONFIG] GOOGLE_APPLICATION_CREDENTIALS: %s", "***" if GOOGLE_APPLICATION_CREDENTIALS else "NOT_SET")
logger.info("[CONFIG] DEFAULT_STORAGE_PROVIDER: %s", DEFAULT_STORAGE_PROVIDER)
logger.info("[CONFIG] AWS_S3_BUCKET_NAME: %s", "***" if AWS_S3_BUCKET_NAME else "NOT_SET")
logger.info("[CONFIG] AWS_REGION: %s", AWS_REGION)
logger.info("[CONFIG] AWS_S3_PREFIX: %s", AWS_S3_PREFIX)