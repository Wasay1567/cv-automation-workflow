import os
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from io import BytesIO
from app.services.google_auth import drive_service
from app.core.config import PARENT_FOLDER_ID
from googleapiclient.http import MediaIoBaseUpload # Moved to top for better practice

from googleapiclient.http import MediaIoBaseDownload

# Setup Jinja2 environment
# Assuming this file is in app/services/
template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
env = Environment(loader=FileSystemLoader(template_dir))

def download_file_from_drive(file_id: str):
    request = drive_service.files().get_media(fileId=file_id)
    file_stream = BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        
    file_stream.seek(0)
    return file_stream


def generate_and_upload_cv(data: dict):
    # 1. Render HTML with Jinja2
    template = env.get_template('cv_template.html')
    html_content = template.render(data)

    # 2. Convert HTML to PDF in memory
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)

    # Check for errors
    if pisa_status.err:
        raise Exception("Error generating PDF with xhtml2pdf")

    # IMPORTANT: Go back to the start of the stream before uploading
    pdf_buffer.seek(0)

    file_name = f"{data.get('name', 'Generated')}_2025_CV.pdf"
    
    # --- NEW: Check and Delete Existing File ---
    try:
        # Search for files with the same name in the specific parent folder
        query = f"name = '{file_name}' and '{PARENT_FOLDER_ID}' in parents and trashed = false"
        results = drive_service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name)'
        ).execute()
        
        items = results.get('files', [])
        
        for item in items:
            print(f"Found existing CV: {item['name']} (ID: {item['id']}). Deleting...")
            drive_service.files().delete(fileId=item['id']).execute()
            
    except Exception as e:
        print(f"Warning during file cleanup: {e}")
    # --------------------------------------------

    # Proceed with Upload
    file_metadata = {
        'name': file_name,
        'mimeType': 'application/pdf',
        'parents': [PARENT_FOLDER_ID] if PARENT_FOLDER_ID else []
    }
    
    media = MediaIoBaseUpload(pdf_buffer, mimetype='application/pdf', resumable=True)
    
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    return file.get('id')