# CV Generation Backend

FastAPI microservice for generating and storing CV PDFs. Supports PDF generation via Playwright browser rendering, with idempotent storage in AWS S3 or Google Drive.

## Setup

### Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### Environment Configuration
Create `.env` file in backend directory:

```env
# Logging
LOG_LEVEL=INFO

# AWS S3 Configuration
DEFAULT_STORAGE_PROVIDER=s3
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
AWS_S3_PREFIX=cvs

# Google Drive Configuration (optional)
GOOGLE_DRIVE_FOLDER_ID=your-folder-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## Running

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Generate & Upload CV
**POST** `/generate-pdf`
```json
{
  "student_id": "STU-0001",
  "name": "John Doe",
  "profession": "Software Engineer",
  "email": "john@example.com",
  "phone": "+1-234-567-8900",
  "address": "123 Main St",
  "about_me": "Brief bio...",
  "profile_image_url": "https://...",
  "skills": [{"name": "Python"}, {"name": "FastAPI"}],
  "languages": [{"name": "English", "percent": 95}],
  "certificates": ["AWS Certified"],
  "personality_score": 8,
  "experience": [{
    "date": "(2020-2023)",
    "title": "Engineer",
    "company": "Tech Corp",
    "description": "Responsibilities..."
  }],
  "education": [{
    "date": "(2018-2022)",
    "degree": "BS Engineering",
    "institution": "University",
    "description": "GPA: 3.8"
  }]
}
```

Query param: `provider=s3` or `provider=google_drive` (defaults to env `DEFAULT_STORAGE_PROVIDER`)

Response:
```json
{
  "status": "success",
  "provider": "s3",
  "object_id": "cvs/STU-0001.pdf",
  "file_name": "STU-0001.pdf",
  "size_bytes": 245123,
  "student_name": "John Doe"
}
```

### Download CV
**POST** `/download`
```json
{
  "object_id": "cvs/STU-0001.pdf"
}
```
Or use student_id:
```json
{
  "student_id": "STU-0001"
}
```

Returns PDF file stream for download.

## Features

- **Idempotent Storage**: One PDF per student. New generation replaces old file automatically.
- **Dual Storage Support**: S3 and Google Drive with pluggable interface.
- **Comprehensive Logging**: Structured logging with request IDs, timing, error tracebacks.
- **Error Handling**: Custom exception types, detailed error messages, HTTP status codes.
- **CORS Enabled**: Cross-origin support for frontend integration.
- **Playwright PDF Generation**: Browser-based rendering for accurate CSS/layout.

## Storage Idempotency

Student CV files are named by `student_id.pdf`. When a new generation request arrives:

1. **S3**: Delete existing object with key `cvs/{student_id}.pdf`, then upload new
2. **Google Drive**: Find and delete existing file by name, then upload new

One PDF per student guaranteed.

## Error Handling

All errors include:
- Status code (400, 404, 500, 503)
- Error code (e.g., `STORAGE_ERROR`, `PDF_GENERATION_ERROR`)
- Human-readable message
- Request ID for tracing

## Logging

Set `LOG_LEVEL` env var: `DEBUG`, `INFO`, `WARNING`, `ERROR`

Logs include:
- Request method, path, duration
- Service initialization and validation
- PDF generation and upload steps
- Storage provider operations
- Full tracebacks on errors
