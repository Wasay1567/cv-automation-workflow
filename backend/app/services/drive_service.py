from app.services.google_auth import drive_service
from app.core.config import PARENT_FOLDER_ID

def copy_template(template_id: str, name: str):
    body = {
        "name": f"{name}_CV",
        "parents": [PARENT_FOLDER_ID] if PARENT_FOLDER_ID else []
    }

    file = drive_service.files().copy(
        fileId=template_id,
        body=body,
        fields="id"
    ).execute()

    return file["id"]