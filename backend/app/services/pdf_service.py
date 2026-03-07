import os
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from io import BytesIO
from app.services.google_auth import drive_service
from app.core.config import PARENT_FOLDER_ID
from googleapiclient.http import MediaIoBaseUpload # Moved to top for better practice

# Setup Jinja2 environment
# Assuming this file is in app/services/
template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
env = Environment(loader=FileSystemLoader(template_dir))

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

    # 3. Upload to Google Drive
    file_metadata = {
        'name': f"{data.get('name', 'Generated').replace(' ', '_')}_CV.pdf",
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