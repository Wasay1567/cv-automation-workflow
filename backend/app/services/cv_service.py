from datetime import date, datetime
import asyncio
import json
import logging
import os
import re
from typing import Any
from uuid import UUID
from urllib.parse import quote, unquote, urlparse

import boto3
import httpx
from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import app.database as database
from app.services.email_service import EmailService
from app.models import (
    Academic, Achievement, CVStatus, CVSubmission, Certificate,
    ExtraCurricular, FYP, IndustrialVisit, Internship, PersonalInfo,
    Reference, Skill, User, UserRole,
)

logger = logging.getLogger(__name__)

PDF_SERVICE_URL = "http://172.31.79.198:8080"

CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png"
}


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def _s3_bucket() -> str:
    bucket = os.getenv("AWS_S3_BUCKET_NAME")
    if not bucket:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET_NAME is not configured")
    return bucket


def _s3_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"


def _s3_client():
    return boto3.client("s3", region_name=_s3_region())


def _photo_extension(filename: str | None, content_type: str | None) -> str:
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext:
            return ext
    return CONTENT_TYPE_TO_EXTENSION.get((content_type or "").lower(), "")


def _photo_key(student_id: UUID, filename: str | None, content_type: str | None) -> str:
    ext = _photo_extension(filename, content_type)
    if not ext:
        raise HTTPException(status_code=400, detail="student_image must be a supported image type")
    return f"profile-photo/{student_id}{ext}"


def _photo_url(key: str) -> str:
    return f"https://{_s3_bucket()}.s3.{_s3_region()}.amazonaws.com/{quote(key)}"


def _s3_key_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.netloc or "amazonaws.com" not in parsed.netloc:
        return None
    key = parsed.path.lstrip("/")
    return unquote(key) if key else None


def _upload_photo(image_bytes: bytes, key: str, content_type: str | None) -> str:
    kwargs: dict[str, Any] = {"Bucket": _s3_bucket(), "Key": key, "Body": image_bytes}
    if content_type:
        kwargs["ContentType"] = content_type
    _s3_client().put_object(**kwargs)
    return _photo_url(key)


def _delete_s3_object(key: str) -> None:
    _s3_client().delete_object(Bucket=_s3_bucket(), Key=key)


async def _store_student_image(student_id: UUID, image_file: Any) -> tuple[str, str]:
    """Upload profile photo to S3; returns (url, key)."""
    image_bytes = await image_file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="student_image file is empty")

    filename = getattr(image_file, "filename", None)
    content_type = getattr(image_file, "content_type", None)
    key = _photo_key(student_id, filename, content_type)
    url = await run_in_threadpool(_upload_photo, image_bytes, key, content_type)
    return url, key


async def _delete_photo(url: str | None) -> None:
    key = _s3_key_from_url(url)
    if not key:
        return
    try:
        await run_in_threadpool(_delete_s3_object, key)
    except Exception:
        logger.exception("Failed to delete profile photo key=%s", key)


# ---------------------------------------------------------------------------
# Background task helpers
# ---------------------------------------------------------------------------

def _log_task_exception(task: asyncio.Task[Any], name: str) -> None:
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        logger.info("Background task '%s' was cancelled", name)
        return
    except Exception:
        logger.exception("Unable to inspect background task '%s' result", name)
        return
    if exc is not None:
        logger.exception("Background task '%s' failed", name, exc_info=exc)


def _schedule_task(coro, name: str) -> None:
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda t: _log_task_exception(t, name))
    logger.info("Scheduled background task '%s'", name)


def _schedule_rejection_email(to_email: str, rejection_comment: str | None) -> None:
    student_name = to_email.split("@")[0]
    _schedule_task(
        run_in_threadpool(EmailService.send_cv_rejection_email, to_email, student_name, rejection_comment),
        "send_rejection_email",
    )
    logger.info("Scheduled rejection email for recipient=%s", to_email)


def _schedule_cv_generation(cv_id: UUID) -> None:
    _schedule_task(_generate_cv_pdf_and_store_file_id(cv_id), "generate_cv_pdf")
    logger.info("Scheduled background CV PDF generation for cv_id=%s", cv_id)


# ---------------------------------------------------------------------------
# Date / formatting utilities
# ---------------------------------------------------------------------------

def _to_iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def _fmt_month_year(value: date | datetime | None) -> str | None:
    return value.strftime("%b %Y") if value else None


def _is_future(value: date | datetime | None) -> bool:
    if value is None:
        return False
    d = value.date() if isinstance(value, datetime) else value
    return d > date.today()


def _date_range(from_date: date | datetime | None, to_date: date | datetime | None) -> str | None:
    start = _fmt_month_year(from_date)
    end = "Present" if _is_future(to_date) or to_date is None else _fmt_month_year(to_date)
    if start and end:
        return f"({start} - {end})"
    if start:
        return f"({start})"
    if end:
        return f"({end})"
    return None


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------

def _normalize_degree(academic: Academic) -> str:
    label = (academic.majors or academic.degree or "").strip()
    if label.lower().startswith("department of"):
        label = re.sub(r"^Department of\s*", "Bachelors of ", label, flags=re.IGNORECASE).strip()
    return label


def _personality_score(cv: CVSubmission) -> int:
    """Score from 5-10 based on how complete the CV is."""
    score = 5
    for field in [
        cv.personal_info,
        cv.academics,
        cv.internships,
        cv.skills,
        cv.achievements or cv.certificates,
        cv.extra_curricular or cv.references,
        cv.career_counseling,
    ]:
        if field:
            score += 1
    return min(score, 10)


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    cleaned = raw.strip()
    # Strip markdown code fences
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# AI summary
# ---------------------------------------------------------------------------

def _get_ai_summary_and_title(cv_data: dict[str, Any]) -> dict[str, str]:
    prompt = (
        "You are a professional resume writer.\n\n"
        "Using the following student information generate:\n\n"
        "1. Professional CV summary (3-4 lines)\n"
        "2. Best job title for the candidate.\n\n"
        "Return JSON:\n\n"
        '{\n "summary": "...",\n "title": "..."\n}\n\n'
        f"Student Data:\n{json.dumps(cv_data, ensure_ascii=True)}"
    )
    try:
        from app.services.gen import get_gemini_response
        parsed = _extract_json_object(get_gemini_response(prompt) or "") or {}
    except Exception:
        logger.exception("AI summary/title generation failed; using empty fallback")
        parsed = {}

    return {
        "summary": (parsed.get("summary") or "").strip(),
        "title": (parsed.get("title") or "").strip(),
    }


# ---------------------------------------------------------------------------
# PDF payload builder
# ---------------------------------------------------------------------------

def _build_pdf_payload(cv: CVSubmission, ai: dict[str, str]) -> dict[str, Any]:
    info = cv.personal_info
    student_email = (cv.student.email if cv.student else None) or (info.email if info else None)
    fallback_name = student_email.split("@")[0] if student_email and "@" in student_email else "Student"

    title = ai.get("title") or (_normalize_degree(cv.academics[0]) if cv.academics else "Student")

    return {
        "student_id": str(cv.student_id),
        "name": (info.name if info and info.name else fallback_name),
        "profession": title,
        "phone": (info.cell if info else "") or "",
        "email": (info.email if info else "") or student_email or "",
        "address": (info.address if info else "") or "",
        "about_me": ai.get("summary") or "",
        "profile_image_url": cv.student_image_url or "",
        "personality_score": _personality_score(cv),
        "skills": [{"name": s.name} for s in cv.skills if s.name],
        "experience": [
            {
                "date": _date_range(i.from_date, i.to_date),
                "title": i.position or i.field or "",
                "company": i.organization or "",
                "description": [d for d in (i.duties or []) if isinstance(d, str) and d.strip()],
            }
            for i in cv.internships
        ],
        "education": [
            {
                "date": _date_range(a.from_date, a.to_date),
                "degree": _normalize_degree(a),
                "institution": a.university or "NED UNIVERSITY OF ENGINEERING AND TECHNOLOGY, KARACHI",
                "description": "",
            }
            for a in cv.academics
        ],
    }


# ---------------------------------------------------------------------------
# Background: PDF generation
# ---------------------------------------------------------------------------

async def _generate_cv_pdf_and_store_file_id(cv_id: UUID) -> None:
    try:
        if database.AsyncSessionLocal is None:
            database.init_db()

        logger.info("Starting CV PDF generation for cv_id=%s", cv_id)
        async with database.AsyncSessionLocal() as session:
            result = await session.execute(
                select(CVSubmission).options(*_cv_load_options()).where(CVSubmission.cv_id == cv_id)
            )
            cv = result.scalar_one_or_none()

            if cv is None:
                logger.warning("CV not found for cv_id=%s — skipping PDF generation", cv_id)
                return

            if cv.status != CVStatus.approved:
                logger.warning("CV %s has status %s — skipping PDF generation", cv_id, cv.status.value)
                return

            ai_result = await run_in_threadpool(_get_ai_summary_and_title, _serialize_cv(cv))
            payload = _build_pdf_payload(cv, ai_result)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{PDF_SERVICE_URL}/generate-pdf", json=payload)
                response.raise_for_status()
                data = response.json() if response.content else {}

            # BUG FIX: was silently ignoring all three keys missing; now logs clearly
            file_id = (
                data.get("file_id")
                or data.get("id")
                or data.get("drive_file_id")
                or data.get("object_id")
            )
            if not file_id:
                logger.error("PDF service response missing file_id for cv_id=%s. Response: %s", cv_id, data)
                return

            cv.cv_drive_url = str(file_id)
            await session.commit()
            logger.info("Stored cv_drive_url for cv_id=%s file_id=%s", cv_id, file_id)

    except httpx.HTTPError:
        logger.exception("PDF generation HTTP error for cv_id=%s", cv_id)
    except Exception:
        logger.exception("Unexpected error during PDF generation for cv_id=%s", cv_id)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _serialize_cv(cv: CVSubmission) -> dict[str, Any]:
    return {
        "cv_id": str(cv.cv_id),
        "student_id": str(cv.student_id),
        "student_email": cv.student.email if cv.student else None,
        "status": cv.status.value,
        "student_image": cv.student_image_url,
        "rejection_comment": cv.rejection_comment,
        "career_counseling": cv.career_counseling,
        "assessment": cv.assessment or [],
        "created_at": _to_iso(cv.created_at),
        "updated_at": _to_iso(cv.updated_at),
        "personal_info": _serialize_personal_info(cv.personal_info),
        "academics": [_serialize_academic(a) for a in cv.academics],
        "internships": [_serialize_internship(i) for i in cv.internships],
        "industrial_visits": [_serialize_visit(v) for v in cv.industrial_visits],
        "fyp": _serialize_fyp(cv.fyp),
        "certificates": [{"id": str(c.id), "cv_id": str(c.cv_id), "name": c.name} for c in cv.certificates],
        "achievements": [{"id": str(a.id), "cv_id": str(a.cv_id), "description": a.description} for a in cv.achievements],
        "skills": [{"id": str(s.id), "cv_id": str(s.cv_id), "name": s.name} for s in cv.skills],
        "extra_curricular": [{"id": str(e.id), "cv_id": str(e.cv_id), "activity": e.activity} for e in cv.extra_curricular],
        "references": [_serialize_reference(r) for r in cv.references],
    }


def _serialize_personal_info(info: PersonalInfo | None) -> dict | None:
    if not info:
        return None
    return {
        "id": str(info.id), "cv_id": str(info.cv_id),
        "name": info.name, "father_name": info.father_name,
        "department": info.department, "batch": info.batch,
        "cell": info.cell, "roll_no": info.roll_no, "cnic": info.cnic,
        "email": info.email, "gender": info.gender,
        "dob": _to_iso(info.dob), "address": info.address,
    }


def _serialize_academic(a: Academic) -> dict:
    return {
        "id": str(a.id), "cv_id": str(a.cv_id),
        "degree": a.degree, "university": a.university,
        "from_date": _to_iso(a.from_date), "to_date": _to_iso(a.to_date),
        "gpa": a.gpa, "majors": a.majors,
    }


def _serialize_internship(i: Internship) -> dict:
    return {
        "id": str(i.id), "cv_id": str(i.cv_id),
        "organization": i.organization, "position": i.position,
        "field": i.field, "duties": i.duties or [],
        "from_date": _to_iso(i.from_date), "to_date": _to_iso(i.to_date),
    }


def _serialize_visit(v: IndustrialVisit) -> dict:
    return {
        "id": str(v.id), "cv_id": str(v.cv_id),
        "organization": v.organization, "purpose": v.purpose,
        "visit_date": _to_iso(v.visit_date),
    }


def _serialize_fyp(fyp: FYP | None) -> dict | None:
    if not fyp:
        return None
    return {
        "id": str(fyp.id), "cv_id": str(fyp.cv_id),
        "title": fyp.title, "company": fyp.company, "objectives": fyp.objectives,
    }


def _serialize_reference(r: Reference) -> dict:
    return {
        "id": str(r.id), "cv_id": str(r.cv_id),
        "name": r.name, "contact": r.contact,
        "occupation": r.occupation, "relation": r.relation,
    }


# Public alias used by other modules
serialize_cv = _serialize_cv


# ---------------------------------------------------------------------------
# CV summary (used in list views)
# ---------------------------------------------------------------------------

def _build_summary(cv: CVSubmission) -> dict[str, Any]:
    bachelors_cgpa = next(
        (a.gpa for a in cv.academics if a.degree and any(d in a.degree.lower() for d in ["bachelor", "bs", "be"])),
        None,
    )
    return {
        "cv_id": str(cv.cv_id),
        "student_email": cv.student.email if cv.student else None,
        "department": (cv.student.department if cv.student else None) or (cv.personal_info.department if cv.personal_info else None),
        "batch": cv.personal_info.batch if cv.personal_info else None,
        "cv_status": cv.status.value,
        "skills": [s.name for s in cv.skills],
        "cgpa": bachelors_cgpa,
        "internships_count": len(cv.internships),
    }


# ---------------------------------------------------------------------------
# CV section attachment (create / update)
# ---------------------------------------------------------------------------

def _normalize_named_list(items: list[Any], key: str) -> list[dict]:
    """Accept list of dicts or plain strings; always return list of dicts."""
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, str):
            result.append({key: item})
    return result


def _attach_cv_sections(cv: CVSubmission, data: dict[str, Any]) -> None:
    info = data.get("personal_info")
    cv.personal_info = PersonalInfo(**info) if info else None
    cv.academics = [Academic(**i) for i in data.get("academics", [])]
    cv.internships = [Internship(**i) for i in data.get("internships", [])]
    cv.industrial_visits = [IndustrialVisit(**i) for i in data.get("industrial_visits", [])]
    cv.fyp = FYP(**data["fyp"]) if data.get("fyp") else None
    cv.certificates = [Certificate(**i) for i in _normalize_named_list(data.get("certificates", []), "name")]
    cv.achievements = [Achievement(**i) for i in _normalize_named_list(data.get("achievements", []), "description")]
    cv.skills = [Skill(**i) for i in _normalize_named_list(data.get("skills", []), "name")]
    cv.extra_curricular = [ExtraCurricular(**i) for i in _normalize_named_list(data.get("extra_curricular", []), "activity")]
    cv.assessment = data.get("assessment") or []
    cv.references = [Reference(**i) for i in data.get("references", [])]


def _cv_load_options() -> list:
    return [
        selectinload(CVSubmission.student),
        selectinload(CVSubmission.personal_info),
        selectinload(CVSubmission.academics),
        selectinload(CVSubmission.internships),
        selectinload(CVSubmission.industrial_visits),
        selectinload(CVSubmission.fyp),
        selectinload(CVSubmission.certificates),
        selectinload(CVSubmission.achievements),
        selectinload(CVSubmission.skills),
        selectinload(CVSubmission.extra_curricular),
        selectinload(CVSubmission.references),
    ]


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

async def create_cv(
    data: dict[str, Any],
    current_user: User,
    db: AsyncSession,
    student_image_file: Any | None = None,
) -> dict[str, Any]:
    # Reuse an existing CV for this student to keep cv_id stable across resubmissions.
    existing_result = await db.execute(
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.student_id == current_user.id)
        .order_by(CVSubmission.updated_at.desc())
    )
    existing_cvs = existing_result.scalars().all()

    cv = existing_cvs[0] if existing_cvs else CVSubmission(student_id=current_user.id)
    old_image_url = cv.student_image_url
    cv.status = CVStatus.pending_advisor
    cv.rejection_comment = None
    cv.career_counseling = data.get("career_counseling", False)
    _attach_cv_sections(cv, data)

    uploaded_key: str | None = None
    if student_image_file is not None:
        cv.student_image_url, uploaded_key = await _store_student_image(current_user.id, student_image_file)
    elif not existing_cvs:
        cv.student_image_url = data.get("student_image")

    if not existing_cvs:
        db.add(cv)

    try:
        await db.commit()
        await db.refresh(cv)
    except Exception:
        await db.rollback()
        if uploaded_key:
            await _delete_photo(cv.student_image_url)
        logger.exception("Failed to create or update CV for student_id=%s", current_user.id)
        raise

    # If extension changed, old key differs, so remove previous object after successful commit.
    if uploaded_key and old_image_url and old_image_url != cv.student_image_url:
        await _delete_photo(old_image_url)

    # Cleanup legacy duplicate rows while preserving the selected canonical CV.
    duplicate_cvs = existing_cvs[1:]
    if duplicate_cvs:
        duplicate_ids = [row.cv_id for row in duplicate_cvs]
        duplicate_photo_urls = [row.student_image_url for row in duplicate_cvs if row.student_image_url]
        try:
            await db.execute(delete(CVSubmission).where(CVSubmission.cv_id.in_(duplicate_ids)))
            await db.commit()
            for duplicate_photo_url in duplicate_photo_urls:
                if duplicate_photo_url != cv.student_image_url:
                    await _delete_photo(duplicate_photo_url)
        except Exception:
            await db.rollback()
            logger.exception("Failed to clean up duplicate CVs for student_id=%s", current_user.id)

    return _serialize_cv(cv)


async def list_cvs(current_user: User, db: AsyncSession) -> list[dict[str, Any]]:
    query = select(CVSubmission).options(*_cv_load_options())

    if current_user.role == UserRole.advisor:
        query = query.join(CVSubmission.student).where(User.department == current_user.department)
    elif current_user.role == UserRole.admin:
        # BUG FIX: original query joined student unnecessarily for admin; simplified
        query = query.where(CVSubmission.status == CVStatus.approved)

    result = await db.execute(query)
    cvs = result.scalars().all()
    return [{**_serialize_cv(cv), "summary": _build_summary(cv)} for cv in cvs]


async def get_student_cvs(current_user: User, db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.student_id == current_user.id)
        .order_by(CVSubmission.updated_at.desc())
    )
    return [_serialize_cv(cv) for cv in result.scalars().all()]


async def get_cv(cv_id: str, current_user: User, db: AsyncSession) -> CVSubmission | None:
    result = await db.execute(
        select(CVSubmission).options(*_cv_load_options()).where(CVSubmission.cv_id == cv_id)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        return None

    # Access control
    if current_user.role == UserRole.student and cv.student_id != current_user.id:
        return None
    if current_user.role == UserRole.advisor and cv.student and cv.student.department != current_user.department:
        return None

    return cv


async def update_cv(
    cv_id: str,
    data: dict[str, Any],
    current_user: User,
    db: AsyncSession,
    student_image_file: Any | None = None,
) -> dict[str, Any] | None:
    result = await db.execute(
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.cv_id == cv_id, CVSubmission.student_id == current_user.id)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        return None

    old_image_url = cv.student_image_url
    cv.career_counseling = data.get("career_counseling", cv.career_counseling)
    cv.status = CVStatus.pending_advisor
    cv.rejection_comment = None
    _attach_cv_sections(cv, data)

    uploaded_key: str | None = None
    new_image_url: str | None = None
    if student_image_file is not None:
        new_image_url, uploaded_key = await _store_student_image(cv.student_id, student_image_file)
        cv.student_image_url = new_image_url

    try:
        await db.commit()
        await db.refresh(cv)
    except Exception:
        await db.rollback()
        if uploaded_key:
            await _delete_photo(new_image_url)
        logger.exception("Failed to update CV cv_id=%s for student_id=%s", cv_id, current_user.id)
        raise

    # Delete old photo only after successful commit
    if uploaded_key and old_image_url and old_image_url != new_image_url:
        await _delete_photo(old_image_url)

    refreshed = await get_cv(cv_id, current_user, db)
    return _serialize_cv(refreshed) if refreshed else None


async def delete_cv(cv_id: str, current_user: User, db: AsyncSession) -> bool:
    result = await db.execute(
        select(CVSubmission).where(CVSubmission.cv_id == cv_id, CVSubmission.student_id == current_user.id)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        return False

    image_url = cv.student_image_url
    await db.delete(cv)
    await db.commit()
    await _delete_photo(image_url)
    return True


async def approve_cv(cv_id: str, current_user: User, db: AsyncSession) -> dict[str, Any] | None:
    cv = await get_cv(cv_id, current_user, db)
    if cv is None:
        return None

    cv.status = CVStatus.approved
    cv.rejection_comment = None
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to approve CV cv_id=%s by user_id=%s", cv_id, current_user.id)
        raise

    try:
        _schedule_cv_generation(cv.cv_id)
    except Exception:
        logger.exception("Failed to schedule PDF generation for cv_id=%s", cv_id)

    return {"cv_id": str(cv.cv_id), "status": cv.status.value, "message": "CV approved successfully"}


async def reject_cv(cv_id: str, comment: str | None, current_user: User, db: AsyncSession) -> dict[str, Any] | None:
    cv = await get_cv(cv_id, current_user, db)
    if cv is None:
        return None

    cv.status = CVStatus.rejected
    cv.rejection_comment = comment
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to reject CV cv_id=%s by user_id=%s", cv_id, current_user.id)
        raise

    email_result = await db.execute(select(User.email).where(User.id == cv.student_id))
    student_email = email_result.scalar_one_or_none()

    if student_email:
        try:
            _schedule_rejection_email(student_email, comment)
        except Exception:
            logger.exception("Failed to schedule rejection email for cv_id=%s", cv_id)
    else:
        logger.warning("Student email not found for cv_id=%s student_id=%s", cv_id, cv.student_id)

    return {
        "cv_id": str(cv.cv_id),
        "status": cv.status.value,
        "rejection_comment": cv.rejection_comment,
        "message": "CV rejected successfully",
    }


# ---------------------------------------------------------------------------
# Bulk download
# ---------------------------------------------------------------------------

async def download_cv_zip(
    cv_ids: list[str],
    current_user: User,
    db: AsyncSession,
    request: Request,
) -> StreamingResponse:
    if not cv_ids:
        raise HTTPException(status_code=400, detail="At least one CV id must be provided")

    student_ids: list[str] = []
    for cv_id in cv_ids:
        cv = await get_cv(cv_id, current_user, db)
        if cv is None:
            raise HTTPException(status_code=404, detail=f"CV '{cv_id}' not found")
        student_ids.append(str(cv.student_id))

    request_id = request.headers.get("X-Request-ID", "unknown")

    async def stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{PDF_SERVICE_URL}/download-zip",
                json={"student_ids": student_ids},
                headers={"X-Request-ID": request_id},
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(
        stream(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="bulk_download.zip"',
            "X-Request-ID": request_id,
            "X-Total-Files": str(len(student_ids)),
        },
    )