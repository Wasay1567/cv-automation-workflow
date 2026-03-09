from fastapi import APIRouter, HTTPException, Body
from app.schemas.cv_schema import CVRequest
from app.core.config import TEMPLATE_ID
from app.services.pdf_service import generate_and_upload_cv, download_file_from_drive
import zipfile
from io import BytesIO  # <--- ADD THIS IMPORT
from fastapi.responses import StreamingResponse
from app.core.config import PARENT_FOLDER_ID
from app.services.google_auth import drive_service

router = APIRouter()

'''
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
    }'''

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


@router.post("/download-single")
async def download_single_cv(payload: dict = Body(...)):
    cv_name = payload.get("cv_name")
    if not cv_name:
        raise HTTPException(status_code=400, detail="CV name is required")

    # Find the file ID by name
    query = f"name = '{cv_name}' and '{PARENT_FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])

    if not files:
        raise HTTPException(status_code=404, detail="CV not found")

    file_id = files[0]['id']
    pdf_content = download_file_from_drive(file_id)

    return StreamingResponse(
        pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={cv_name}"}
    )

@router.post("/download-bulk")
async def download_bulk_cvs(payload: dict = Body(...)):
    year = payload.get("year")
    if not year:
        raise HTTPException(status_code=400, detail="Year is required")

    # Search for all CVs containing the year in their name
    query = f"name contains '{year}' and '{PARENT_FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])

    if not files:
        raise HTTPException(status_code=404, detail=f"No CVs found for year {year}")

    # Create an in-memory ZIP file using BytesIO
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for f in files:
            file_data = download_file_from_drive(f['id'])
            # .getvalue() gets the raw bytes from the BytesIO stream
            zip_file.writestr(f['name'], file_data.getvalue())

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": f"attachment; filename=CVs_{year}.zip"}
    )