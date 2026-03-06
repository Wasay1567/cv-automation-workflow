from fastapi import APIRouter
from app.schemas.cv_schema import CVRequest
from app.services.drive_service import copy_template
from app.services.slides_service import replace_placeholders
from app.core.config import TEMPLATE_ID

router = APIRouter()


@router.post("/generate-cv")
async def generate_cv(data: CVRequest):
    print("Template ID:", TEMPLATE_ID)

    # 1 copy template
    presentation_id = copy_template(TEMPLATE_ID, data.name)

    # 2 replace placeholders
    replace_placeholders(
        presentation_id,
        data.name,
        data.email
    )

    return {
        "status": "CV generated",
        "presentation_id": presentation_id
    }