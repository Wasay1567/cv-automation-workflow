from __future__ import annotations

import logging
import uuid
import traceback
from pathlib import Path

from app.services.storage_service import get_storage_provider
from app.services.generate_sample_pdf import BASE_DIR, render_pdf_from_data

logger = logging.getLogger(__name__)


class PDFGenerationError(Exception):
    """Raised when PDF generation fails."""
    pass


class PDFUploadError(Exception):
    """Raised when PDF upload fails."""
    pass


class PDFDownloadError(Exception):
    """Raised when PDF download fails."""
    pass


def _build_temp_pdf_path(student_id: str) -> Path:
    """Build a unique temporary PDF file path."""
    try:
        temp_dir = BASE_DIR / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex[:10]
        temp_path = temp_dir / f"{student_id}_{token}.pdf"
        logger.debug("[PDF_SERVICE] Created temp path: %s", temp_path)
        return temp_path
    except Exception as exc:
        logger.error("[PDF_SERVICE] Failed to build temp PDF path: %s\n%s", exc, traceback.format_exc())
        raise PDFGenerationError(f"Failed to create temporary directory: {exc}") from exc


def generate_and_upload_cv(data: dict, provider: str | None = None) -> dict:
    # \"\"\"Generate CV PDF from data and upload to storage provider with idempotency.\"\"\"
    student_id = str(data.get("student_id", "")).strip()
    
    if not student_id:
        logger.warning("[PDF_SERVICE] generate_and_upload_cv called without student_id")
        raise ValueError("student_id is required in request payload")

    student_name = data.get("name", student_id).strip()
    temp_pdf = None

    try:
        logger.info("[PDF_SERVICE] Starting CV generation for student: %s (provider: %s)", student_id, provider or "default")
        
        # Build temp path
        temp_pdf = _build_temp_pdf_path(student_id)
        logger.info("[PDF_SERVICE] Temp file path: %s", temp_pdf)

        # 1. Render PDF from template
        try:
            logger.debug("[PDF_SERVICE] Rendering PDF from Jinja2 template...")
            output_path = render_pdf_from_data(data, temp_pdf)
            logger.info("[PDF_SERVICE] PDF rendered successfully: %s (size: %d bytes)", output_path, output_path.stat().st_size)
        except Exception as exc:
            logger.error("[PDF_SERVICE] PDF rendering failed: %s\n%s", exc, traceback.format_exc())
            raise PDFGenerationError(f"Failed to render PDF from template: {exc}") from exc

        # 2. Read PDF bytes
        try:
            pdf_bytes = output_path.read_bytes()
            logger.debug("[PDF_SERVICE] Read PDF bytes: %d bytes", len(pdf_bytes))
        except Exception as exc:
            logger.error("[PDF_SERVICE] Failed to read PDF file: %s\n%s", exc, traceback.format_exc())
            raise PDFGenerationError(f"Failed to read generated PDF: {exc}") from exc

        # 3. Get storage provider
        try:
            logger.debug("[PDF_SERVICE] Initializing storage provider: %s", provider or "default")
            storage = get_storage_provider(provider)
            logger.info("[PDF_SERVICE] Storage provider initialized: %s", storage.provider_name)
        except Exception as exc:
            logger.error("[PDF_SERVICE] Failed to initialize storage provider: %s\n%s", exc, traceback.format_exc())
            raise PDFUploadError(f"Failed to initialize storage provider: {exc}") from exc

        # 4. Upload with idempotency (delete old, upload new)
        try:
            logger.info("[PDF_SERVICE] Uploading CV for student: %s (idempotent mode)", student_id)
            object_id = storage.upload_or_replace_pdf(
                student_id=student_id,
                pdf_bytes=pdf_bytes,
                display_name=student_name,
            )
            logger.info("[PDF_SERVICE] CV uploaded successfully. Object ID: %s", object_id)
            
            result = {
                "provider": storage.provider_name,
                "object_id": object_id,
                "file_name": f"{student_id}.pdf",
                "size_bytes": len(pdf_bytes),
                "student_name": student_name,
            }
            logger.info("[PDF_SERVICE] Generate and upload completed successfully for: %s", student_id)
            return result
            
        except Exception as exc:
            logger.error("[PDF_SERVICE] Upload failed for student %s to provider %s: %s\n%s", student_id, storage.provider_name, exc, traceback.format_exc())
            raise PDFUploadError(f"Failed to upload PDF to {storage.provider_name}: {exc}") from exc

    except (PDFGenerationError, PDFUploadError):
        # Re-raise our custom exceptions
        raise
    except Exception as exc:
        logger.error("[PDF_SERVICE] Unexpected error during generate_and_upload_cv: %s\n%s", exc, traceback.format_exc())
        raise PDFGenerationError(f"Unexpected error: {exc}") from exc
    finally:
        # Cleanup temp file
        if temp_pdf and temp_pdf.exists():
            try:
                temp_pdf.unlink()
                logger.debug("[PDF_SERVICE] Cleaned up temp file: %s", temp_pdf)
            except Exception as exc:
                logger.warning("[PDF_SERVICE] Failed to cleanup temp file %s: %s", temp_pdf, exc)


def download_cv(object_id: str, provider: str | None = None):
    """Download CV PDF from storage provider."""
    if not object_id or not object_id.strip():
        logger.warning("[PDF_SERVICE] download_cv called with empty object_id")
        raise ValueError("object_id is required")

    try:
        logger.info("[PDF_SERVICE] Starting CV download for object: %s (provider: %s)", object_id, provider or "default")
        
        # Initialize storage provider
        try:
            storage = get_storage_provider(provider)
            logger.debug("[PDF_SERVICE] Storage provider initialized: %s", storage.provider_name)
        except Exception as exc:
            logger.error("[PDF_SERVICE] Failed to initialize storage provider for download: %s\n%s", exc, traceback.format_exc())
            raise PDFDownloadError(f"Failed to initialize storage provider: {exc}") from exc

        # Download PDF
        try:
            logger.debug("[PDF_SERVICE] Downloading PDF file from %s...", storage.provider_name)
            pdf_stream = storage.download_pdf(object_id=object_id)
            logger.info("[PDF_SERVICE] PDF downloaded successfully. Size: %d bytes", len(pdf_stream.getvalue()))
            return pdf_stream
        except Exception as exc:
            logger.error("[PDF_SERVICE] Download failed for object %s from %s: %s\n%s", object_id, storage.provider_name, exc, traceback.format_exc())
            raise PDFDownloadError(f"Failed to download PDF from {storage.provider_name}: {exc}") from exc

    except PDFDownloadError:
        raise
    except Exception as exc:
        logger.error("[PDF_SERVICE] Unexpected error during download_cv: %s\n%s", exc, traceback.format_exc())
        raise PDFDownloadError(f"Unexpected error: {exc}") from exc