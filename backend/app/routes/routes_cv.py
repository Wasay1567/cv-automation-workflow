import logging
import traceback
from fastapi import APIRouter, HTTPException, Body, Query, Request
from app.schemas.cv_schema import CVRequest
from app.services.pdf_service import (
    generate_and_upload_cv,
    download_cv,
    PDFGenerationError,
    PDFUploadError,
    PDFDownloadError,
)
from app.services.storage_service import StorageProviderError, S3Error, GoogleDriveError
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()


def error_response(code: str, message: str, status_code: int, request_id: str | None = None) -> JSONResponse:
    """Build structured error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "code": code,
            "message": message,
            "request_id": request_id or "unknown",
        },
    )

@router.post("/generate-pdf")
def generate_pdf_endpoint(
    request: Request,
    data: CVRequest,
    provider: str = Query(default="s3", description="Storage backend: s3 or google_drive"),
):
    """Generate CV PDF from request data and upload to storage provider."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    student_id = data.student_id
    student_name = data.name
    
    try:
        logger.info(
            "[ROUTE_GENERATE] Starting CV generation for student %s | Request-ID: %s | Provider: %s",
            student_id,
            request_id,
            provider,
        )
        
        cv_data = data.model_dump() if hasattr(data, 'model_dump') else data.dict()
        logger.debug("[ROUTE_GENERATE] CV data payload received with %d fields", len(cv_data))
        
        try:
            result = generate_and_upload_cv(cv_data, provider=provider)
            logger.info(
                "[ROUTE_GENERATE] CV generated and uploaded successfully | Student: %s | Object-ID: %s | Request-ID: %s",
                student_id,
                result.get("object_id"),
                request_id,
            )
            return {
                "status": "success",
                "request_id": request_id,
                **result,
            }
        except PDFGenerationError as exc:
            logger.error(
                "[ROUTE_GENERATE] PDF generation failed for student %s: %s | Request-ID: %s\n%s",
                student_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            return error_response(
                code="PDF_GENERATION_ERROR",
                message=f"Failed to generate PDF: {str(exc)}",
                status_code=400,
                request_id=request_id,
            )
        except PDFUploadError as exc:
            logger.error(
                "[ROUTE_GENERATE] PDF upload failed for student %s: %s | Request-ID: %s\n%s",
                student_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            return error_response(
                code="PDF_UPLOAD_ERROR",
                message=f"Failed to upload PDF: {str(exc)}",
                status_code=500,
                request_id=request_id,
            )
        except (S3Error, GoogleDriveError, StorageProviderError) as exc:
            logger.error(
                "[ROUTE_GENERATE] Storage provider error for student %s: %s | Request-ID: %s\n%s",
                student_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            return error_response(
                code="STORAGE_ERROR",
                message=f"Storage provider error: {str(exc)}",
                status_code=503,
                request_id=request_id,
            )
        except ValueError as exc:
            logger.warning(
                "[ROUTE_GENERATE] Invalid input for student %s: %s | Request-ID: %s",
                student_id,
                exc,
                request_id,
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=f"Invalid input: {str(exc)}",
                status_code=400,
                request_id=request_id,
            )
        except Exception as exc:
            logger.error(
                "[ROUTE_GENERATE] Unexpected error generating CV for student %s: %s | Request-ID: %s\n%s",
                student_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            return error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred. Please try again later.",
                status_code=500,
                request_id=request_id,
            )
    except ValidationError as exc:
        logger.warning(
            "[ROUTE_GENERATE] Request validation failed: %s | Request-ID: %s",
            exc,
            request_id,
        )
        return error_response(
            code="REQUEST_VALIDATION_ERROR",
            message="Invalid request format: " + str(exc.errors()[0] if exc.errors() else exc),
            status_code=422,
            request_id=request_id,
        )
    except Exception as exc:
        logger.error(
            "[ROUTE_GENERATE] Critical error: %s | Request-ID: %s\n%s",
            exc,
            request_id,
            traceback.format_exc(),
        )
        return error_response(
            code="CRITICAL_ERROR",
            message="A critical error occurred. Please contact support.",
            status_code=500,
            request_id=request_id,
        )


@router.post("/download")
async def download_single_cv(
    request: Request,
    payload: dict = Body(...),
    provider: str = Query(default="s3", description="Storage backend: s3 or google_drive"),
):
    """Download CV PDF from storage provider."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    object_id = payload.get("object_id")
    student_id = payload.get("student_id")

    try:
        # Validate input
        if not object_id and not student_id:
            logger.warning(
                "[ROUTE_DOWNLOAD] Missing both object_id and student_id | Request-ID: %s",
                request_id,
            )
            return error_response(
                code="MISSING_PARAMETER",
                message="Either 'object_id' or 'student_id' is required in request body",
                status_code=400,
                request_id=request_id,
            )

        resolved_object_id = object_id or f"cvs/{student_id}.pdf"
        
        logger.info(
            "[ROUTE_DOWNLOAD] Starting download for object_id: %s (student: %s) | Request-ID: %s | Provider: %s",
            resolved_object_id,
            student_id or "unknown",
            request_id,
            provider,
        )

        try:
            pdf_content = download_cv(resolved_object_id, provider=provider)
            logger.info(
                "[ROUTE_DOWNLOAD] CV downloaded successfully for object_id: %s | Size: %d bytes | Request-ID: %s",
                resolved_object_id,
                len(pdf_content.getvalue()),
                request_id,
            )
            
            filename = f"{student_id or 'cv'}.pdf"
            return StreamingResponse(
                pdf_content,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        except PDFDownloadError as exc:
            logger.error(
                "[ROUTE_DOWNLOAD] PDF download failed for object %s: %s | Request-ID: %s\n%s",
                resolved_object_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            return error_response(
                code="PDF_DOWNLOAD_ERROR",
                message=f"Failed to download PDF: {str(exc)}",
                status_code=404,
                request_id=request_id,
            )
        except (S3Error, GoogleDriveError, StorageProviderError) as exc:
            logger.error(
                "[ROUTE_DOWNLOAD] Storage provider error for object %s: %s | Request-ID: %s\n%s",
                resolved_object_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            status_code = 404 if "not found" in str(exc).lower() else 503
            return error_response(
                code="STORAGE_ERROR",
                message=f"Storage provider error: {str(exc)}",
                status_code=status_code,
                request_id=request_id,
            )
        except ValueError as exc:
            logger.warning(
                "[ROUTE_DOWNLOAD] Invalid input for object %s: %s | Request-ID: %s",
                resolved_object_id,
                exc,
                request_id,
            )
            return error_response(
                code="VALIDATION_ERROR",
                message=f"Invalid input: {str(exc)}",
                status_code=400,
                request_id=request_id,
            )
        except Exception as exc:
            logger.error(
                "[ROUTE_DOWNLOAD] Unexpected error downloading CV for object %s: %s | Request-ID: %s\n%s",
                resolved_object_id,
                exc,
                request_id,
                traceback.format_exc(),
            )
            return error_response(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred. Please try again later.",
                status_code=500,
                request_id=request_id,
            )
    except Exception as exc:
        logger.error(
            "[ROUTE_DOWNLOAD] Critical error: %s | Request-ID: %s\n%s",
            exc,
            request_id,
            traceback.format_exc(),
        )
        return error_response(
            code="CRITICAL_ERROR",
            message="A critical error occurred. Please contact support.",
            status_code=500,
            request_id=request_id,
        )