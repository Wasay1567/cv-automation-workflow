import os
import logging
from functools import lru_cache

from google.oauth2 import service_account
from googleapiclient.discovery import build
import app.core.config as config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_credentials():
    """
    Load service account credentials from the file path specified in 
    the GOOGLE_APPLICATION_CREDENTIALS environment variable.
    
    Returns:
        google.oauth2.service_account.Credentials: Service account credentials
        
    Raises:
        ValueError: If GOOGLE_APPLICATION_CREDENTIALS is not set
        FileNotFoundError: If the credentials file doesn't exist
    """
    creds_path = config.GOOGLE_APPLICATION_CREDENTIALS
    
    if not creds_path:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS environment variable is not set. "
            "Please set it to the path of your service account JSON key file."
        )
    
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Service account credentials file not found at: {creds_path}"
        )
    
    logger.info("Loading service account credentials from: %s", creds_path)
    
    credentials = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=SCOPES
    )
    
    return credentials


def validate_folder_access(service, folder_id: str) -> bool:
    """
    Validate that the service account has access to the specified folder.
    
    Args:
        service: Google Drive service instance
        folder_id: The folder ID to validate
        
    Returns:
        bool: True if accessible, False otherwise
    """
    if not folder_id:
        logger.error("GOOGLE_DRIVE_FOLDER_ID is not set")
        return False
    
    try:
        folder = service.files().get(fileId=folder_id, fields="id,name,capabilities").execute()
        can_add_children = folder.get('capabilities', {}).get('canAddChildren', False)
        
        if can_add_children:
            logger.info(
                "✓ Service account has access to folder: %s (ID: %s)",
                folder.get('name'),
                folder_id
            )
            return True
        else:
            logger.error(
                "✗ Service account cannot add files to folder: %s (ID: %s). "
                "Ensure the folder is shared with the service account as Editor.",
                folder.get('name'),
                folder_id
            )
            return False
            
    except Exception as e:
        logger.error(
            "✗ Cannot access folder (ID: %s). Error: %s\n"
            "SOLUTION: Share this Google Drive folder with your service account email as Editor.\n"
            "Service account email: Check your JSON key file for 'client_email' field.",
            folder_id,
            str(e)
        )
        return False


@lru_cache(maxsize=1)
def get_drive_service():
    """Build and cache Google Drive client only when explicitly requested."""
    credentials = get_credentials()
    service = build("drive", "v3", credentials=credentials)
    logger.info("Google Drive service initialized successfully")

    # Validate folder access only when folder id is provided.
    if config.PARENT_FOLDER_ID:
        validate_folder_access(service, config.PARENT_FOLDER_ID)

    return service
