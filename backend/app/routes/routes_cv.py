import logging
import traceback
from fastapi import APIRouter, Body, Query, Request
from app.schemas.cv_schema import CVRequest
from app.services.pdf_service import (
    generate_and_upload_cv,
    PDFGenerationError,
    PDFUploadError,
    BulkDownloadError,
    stream_bulk_cv_zip,
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


@router.post("/download-zip")
async def download_bulk_cv_zip(
    request: Request,
    payload: dict = Body(...),
    provider: str = Query(default="s3", description="Storage backend: s3 or google_drive"),
):
    """Download a ZIP containing CV PDFs for multiple student IDs from S3."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    student_ids = payload.get("student_ids")

    try:
        if not isinstance(student_ids, list):
            logger.warning(
                "[ROUTE_BULK_DOWNLOAD] Invalid payload type for student_ids | Request-ID: %s",
                request_id,
            )
            return error_response(
                code="VALIDATION_ERROR",
                message="'student_ids' is required and must be a list",
                status_code=400,
                request_id=request_id,
            )

        normalized_ids = [str(x).strip() for x in student_ids if str(x).strip()]
        if not normalized_ids:
            logger.warning("[ROUTE_BULK_DOWNLOAD] Empty student_ids list | Request-ID: %s", request_id)
            return error_response(
                code="VALIDATION_ERROR",
                message="'student_ids' must contain at least one non-empty value",
                status_code=400,
                request_id=request_id,
            )

        deduped_count = len(dict.fromkeys(normalized_ids))
        logger.info(
            "[ROUTE_BULK_DOWNLOAD] Starting ZIP download for %d student IDs | Request-ID: %s | Provider: %s",
            deduped_count,
            request_id,
            provider,
        )

        try:
            zip_chunks, included_ids = stream_bulk_cv_zip(normalized_ids, provider=provider)
            logger.info(
                "[ROUTE_BULK_DOWNLOAD] ZIP stream ready with %d files | Request-ID: %s",
                len(included_ids),
                request_id,
            )

            headers = {
                "Content-Disposition": 'attachment; filename="bulk_download.zip"',
                "Content-Type": "application/zip",
                "X-Request-ID": request_id,
                "X-Total-Files": str(len(included_ids)),
            }
            return StreamingResponse(zip_chunks, media_type="application/zip", headers=headers)
        except BulkDownloadError as exc:
            logger.error(
                "[ROUTE_BULK_DOWNLOAD] Bulk download failed: %s | Request-ID: %s\n%s",
                exc,
                request_id,
                traceback.format_exc(),
            )
            status_code = 404 if "not found" in str(exc).lower() else 400
            return error_response(
                code="BULK_DOWNLOAD_ERROR",
                message=str(exc),
                status_code=status_code,
                request_id=request_id,
            )
        except (S3Error, GoogleDriveError, StorageProviderError) as exc:
            logger.error(
                "[ROUTE_BULK_DOWNLOAD] Storage provider error: %s | Request-ID: %s\n%s",
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
                "[ROUTE_BULK_DOWNLOAD] Invalid input: %s | Request-ID: %s",
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
                "[ROUTE_BULK_DOWNLOAD] Unexpected error downloading ZIP: %s | Request-ID: %s\n%s",
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
            "[ROUTE_BULK_DOWNLOAD] Critical error: %s | Request-ID: %s\n%s",
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