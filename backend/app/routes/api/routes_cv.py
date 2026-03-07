from fastapi import APIRouter
from app.schemas.cv_schema import CVRequest
from app.services.drive_service import copy_template
from app.services.slides_service import replace_placeholders
from app.core.config import TEMPLATE_ID
from app.services.pdf_service import generate_and_upload_cv

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

@router.post("/generate-pdf")
async def generate_pdf_endpoint(data: CVRequest):
    # model_dump() is for Pydantic V2. Use .dict() if on V1.
    cv_data = data.model_dump() if hasattr(data, 'model_dump') else data.dict()
    
    # DEBUG: This will print all keys to your terminal. 
    # Ensure you see 'about_me', 'skills', 'experience' here.
    print("Keys being sent to template:", cv_data.keys())

    # Generate the PDF
    file_id = generate_and_upload_cv(cv_data)

    return {"status": "success", "file_id": file_id}