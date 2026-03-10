from datetime import date, datetime
import asyncio
import json
import logging
import re
from typing import Any
from uuid import UUID

import httpx
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import app.database as database
from app.services.email_service import EmailService
from app.models import (
    Academic,
    Achievement,
    CVStatus,
    CVSubmission,
    Certificate,
    ExtraCurricular,
    FYP,
    IndustrialVisit,
    Internship,
    PersonalInfo,
    Reference,
    Skill,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)


def _log_task_exception(task: asyncio.Task[Any], task_name: str) -> None:
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        logger.info("Background task '%s' was cancelled", task_name)
        return
    except Exception:
        logger.exception("Unable to inspect background task '%s' result", task_name)
        return

    if exc is not None:
        logger.exception("Background task '%s' failed", task_name, exc_info=exc)


def _schedule_rejection_email(to_email: str, rejection_comment: str | None) -> None:
    student_name = to_email.split("@")[0] if to_email else "Student"
    task = asyncio.create_task(
        run_in_threadpool(
            EmailService.send_cv_rejection_email,
            to_email,
            student_name,
            rejection_comment,
        )
    )
    task.add_done_callback(lambda t: _log_task_exception(t, "send_rejection_email"))
    logger.info("Scheduled rejection email for recipient=%s", to_email)


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _get_ai_summary_and_title(cv_data: dict[str, Any]) -> dict[str, str]:
    prompt = (
        "You are a professional resume writer.\n\n"
        "Using the following student information generate:\n\n"
        "1. Professional CV summary (3-4 lines)\n"
        "2. Best job title for the candidate.\n\n"
        "Return JSON:\n\n"
        "{\n"
        ' "summary": "...",\n'
        ' "title": "..."\n'
        "}\n\n"
        "Student Data:\n"
        f"{json.dumps(cv_data, ensure_ascii=True)}"
    )

    try:
        from app.services.gen import get_gemini_response

        raw_response = get_gemini_response(prompt)
        parsed = _extract_json_object(raw_response or "") or {}
    except Exception:
        logger.exception("AI summary/title generation failed; using empty fallback values")
        parsed = {}

    summary = parsed.get("summary") if isinstance(parsed.get("summary"), str) else ""
    title = parsed.get("title") if isinstance(parsed.get("title"), str) else ""
    return {"summary": summary.strip(), "title": title.strip()}


def _build_pdf_payload(cv_data: dict[str, Any], ai_result: dict[str, str]) -> dict[str, Any]:
    personal_info = cv_data.get("personal_info") or {}
    internships = cv_data.get("internships") or []
    academics = cv_data.get("academics") or []
    certificates = cv_data.get("certificates") or []
    skills = cv_data.get("skills") or []

    student_email = cv_data.get("student_email") or personal_info.get("email")
    inferred_name = (student_email.split("@")[0] if isinstance(student_email, str) and "@" in student_email else "Student")

    payload: dict[str, Any] = {
        "name": personal_info.get("name") or inferred_name,
        "profession": ai_result.get("title") or "Student",
        "phone": personal_info.get("cell") or "",
        "email": personal_info.get("email") or student_email or "",
        "address": personal_info.get("address") or "",
        "about_me": ai_result.get("summary") or "",
        "profile_image_url": cv_data.get("student_image") or "",
        "skills": [item.get("name") for item in skills if isinstance(item, dict) and item.get("name")],
        "experience": [
            {
                "company": internship.get("organization"),
                "from_date": internship.get("from_date"),
                "to_date": internship.get("to_date"),
                "title": internship.get("position") or internship.get("field") or "",
                "description": "; ".join((internship.get("duties") or [])),
            }
            for internship in internships
            if isinstance(internship, dict)
        ],
        "education": [
            {
                "institution": academic.get("university"),
                "from_date": academic.get("from_date"),
                "to_date": academic.get("to_date"),
                "degree": academic.get("degree"),
                "majors": academic.get("majors"),
            }
            for academic in academics
            if isinstance(academic, dict)
        ],
    }

    certificate_names = [
        item.get("name") for item in certificates if isinstance(item, dict) and item.get("name")
    ]
    if certificate_names:
        payload["certificates"] = certificate_names

    return payload


async def _generate_cv_pdf_and_store_file_id(cv_id: UUID) -> None:
    try:
        if database.AsyncSessionLocal is None:
            database.init_db()

        logger.info("Starting background CV PDF generation for cv_id=%s", cv_id)
        async with database.AsyncSessionLocal() as session:
            result = await session.execute(
                select(CVSubmission)
                .options(*_cv_load_options())
                .where(CVSubmission.cv_id == cv_id)
            )
            cv = result.scalar_one_or_none()
            if cv is None:
                logger.warning("Skipping PDF generation: CV not found for cv_id=%s", cv_id)
                return

            if cv.status != CVStatus.approved:
                logger.warning(
                    "Skipping PDF generation: CV status is %s for cv_id=%s",
                    cv.status.value,
                    cv_id,
                )
                return

            serialized = _serialize_cv(cv)
            ai_result = await run_in_threadpool(_get_ai_summary_and_title, serialized)
            pdf_payload = _build_pdf_payload(serialized, ai_result)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post("http://localhost:5000/generate-pdf", json=pdf_payload)
                response.raise_for_status()
                response_data = response.json() if response.content else {}

            file_id = (
                response_data.get("file_id")
                or response_data.get("id")
                or response_data.get("drive_file_id")
            )
            if not file_id:
                logger.error("PDF generator response missing file id for cv_id=%s", cv_id)
                return

            cv.cv_drive_url = str(file_id)
            await session.commit()
            logger.info(
                "Stored generated CV drive file id for cv_id=%s file_id=%s",
                cv_id,
                file_id,
            )
    except httpx.HTTPError:
        logger.exception("PDF generation HTTP call failed for cv_id=%s", cv_id)
    except Exception:
        logger.exception("Unexpected error while generating/storing CV PDF for cv_id=%s", cv_id)


def _schedule_cv_generation(cv_id: UUID) -> None:
    task = asyncio.create_task(_generate_cv_pdf_and_store_file_id(cv_id))
    task.add_done_callback(lambda t: _log_task_exception(t, "generate_cv_pdf"))
    logger.info("Scheduled background CV PDF generation for cv_id=%s", cv_id)


def _to_iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_cv(cv: CVSubmission) -> dict[str, Any]:
    return {
        "cv_id": str(cv.cv_id),
        "student_id": str(cv.student_id),
        "student_email": cv.student.email if cv.student else None,
        "status": cv.status.value,
        "student_image": cv.student_image_url,
        "rejection_comment": cv.rejection_comment,
        "career_counseling": cv.career_counseling,
        "created_at": _to_iso(cv.created_at),
        "updated_at": _to_iso(cv.updated_at),
        "personal_info": {
            "id": str(cv.personal_info.id),
            "cv_id": str(cv.personal_info.cv_id),
            "name": cv.personal_info.name,
            "father_name": cv.personal_info.father_name,
            "department": cv.personal_info.department,
            "batch": cv.personal_info.batch,
            "cell": cv.personal_info.cell,
            "roll_no": cv.personal_info.roll_no,
            "cnic": cv.personal_info.cnic,
            "email": cv.personal_info.email,
            "gender": cv.personal_info.gender,
            "dob": _to_iso(cv.personal_info.dob),
            "address": cv.personal_info.address,
        }
        if cv.personal_info
        else None,
        "academics": [
            {
                "id": str(academic.id),
                "cv_id": str(academic.cv_id),
                "degree": academic.degree,
                "university": academic.university,
                "from_date": _to_iso(academic.from_date),
                "to_date": _to_iso(academic.to_date),
                "gpa": academic.gpa,
                "majors": academic.majors,
            }
            for academic in cv.academics
        ],
        "internships": [
            {
                "id": str(internship.id),
                "cv_id": str(internship.cv_id),
                "organization": internship.organization,
                "position": internship.position,
                "field": internship.field,
                "duties": internship.duties or [],
                "from_date": _to_iso(internship.from_date),
                "to_date": _to_iso(internship.to_date),
            }
            for internship in cv.internships
        ],
        "industrial_visits": [
            {
                "id": str(visit.id),
                "cv_id": str(visit.cv_id),
                "organization": visit.organization,
                "purpose": visit.purpose,
                "visit_date": _to_iso(visit.visit_date),
            }
            for visit in cv.industrial_visits
        ],
        "fyp": {
            "id": str(cv.fyp.id),
            "cv_id": str(cv.fyp.cv_id),
            "title": cv.fyp.title,
            "company": cv.fyp.company,
            "objectives": cv.fyp.objectives,
        }
        if cv.fyp
        else None,
        "certificates": [
            {"id": str(certificate.id), "cv_id": str(certificate.cv_id), "name": certificate.name}
            for certificate in cv.certificates
        ],
        "achievements": [
            {
                "id": str(achievement.id),
                "cv_id": str(achievement.cv_id),
                "description": achievement.description,
            }
            for achievement in cv.achievements
        ],
        "skills": [
            {"id": str(skill.id), "cv_id": str(skill.cv_id), "name": skill.name}
            for skill in cv.skills
        ],
        "extra_curricular": [
            {
                "id": str(activity.id),
                "cv_id": str(activity.cv_id),
                "activity": activity.activity,
            }
            for activity in cv.extra_curricular
        ],
        "references": [
            {
                "id": str(reference.id),
                "cv_id": str(reference.cv_id),
                "name": reference.name,
                "contact": reference.contact,
                "occupation": reference.occupation,
                "relation": reference.relation,
            }
            for reference in cv.references
        ],
    }


def serialize_cv(cv: CVSubmission) -> dict[str, Any]:
    return _serialize_cv(cv)


def _build_summary(cv: CVSubmission) -> dict[str, Any]:
    bachelors_cgpa = None
    for academic in cv.academics:
        if academic.degree and any(deg in academic.degree.lower() for deg in ["bachelor", "bs", "be"]):
            bachelors_cgpa = academic.gpa
            break

    return {
        "cv_id": str(cv.cv_id),
        "student_email": cv.student.email if cv.student else None,
        "department": (cv.student.department if cv.student else None)
        or (cv.personal_info.department if cv.personal_info else None),
        "batch": cv.personal_info.batch if cv.personal_info else None,
        "cv_status": cv.status.value,
        "skills": [skill.name for skill in cv.skills],
        "cgpa": bachelors_cgpa,
        "internships_count": len(cv.internships),
    }


def _attach_cv_sections(cv: CVSubmission, data: dict[str, Any]) -> None:
    def _normalize_named_items(items: list[Any], key: str) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({key: item})
        return normalized

    personal_info = data.get("personal_info")
    cv.personal_info = PersonalInfo(**personal_info) if personal_info else None

    cv.academics = [Academic(**item) for item in data.get("academics", [])]
    cv.internships = [Internship(**item) for item in data.get("internships", [])]
    cv.industrial_visits = [IndustrialVisit(**item) for item in data.get("industrial_visits", [])]
    cv.fyp = FYP(**data["fyp"]) if data.get("fyp") else None
    cv.certificates = [
        Certificate(**item) for item in _normalize_named_items(data.get("certificates", []), "name")
    ]
    cv.achievements = [
        Achievement(**item) for item in _normalize_named_items(data.get("achievements", []), "description")
    ]
    cv.skills = [
        Skill(**item) for item in _normalize_named_items(data.get("skills", []), "name")
    ]
    cv.extra_curricular = [
        ExtraCurricular(**item) for item in _normalize_named_items(data.get("extra_curricular", []), "activity")
    ]
    cv.references = [Reference(**item) for item in data.get("references", [])]


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


async def create_cv(data: dict[str, Any], current_user: User, db: AsyncSession) -> dict[str, Any]:
    existing_cv_ids_result = await db.execute(
        select(CVSubmission.cv_id).where(CVSubmission.student_id == current_user.id)
    )
    existing_cv_ids = list(existing_cv_ids_result.scalars().all())

    cv = CVSubmission(
        student_id=current_user.id,
        status=CVStatus.pending_advisor,
        student_image_url=data.get("student_image"),
        career_counseling=data.get("career_counseling", False),
    )
    _attach_cv_sections(cv, data)

    db.add(cv)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to create CV for student_id=%s", current_user.id)
        raise

    result = await db.execute(
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.cv_id == cv.cv_id)
    )
    created_cv = result.scalar_one()

    if existing_cv_ids:
        await db.execute(
            delete(CVSubmission).where(CVSubmission.cv_id.in_(existing_cv_ids))
        )
        await db.commit()

    return _serialize_cv(created_cv)


async def list_cvs(current_user: User, db: AsyncSession) -> list[dict[str, Any]]:
    query = select(CVSubmission).options(*_cv_load_options())

    if current_user.role == UserRole.advisor:
        query = query.join(CVSubmission.student).where(User.department == current_user.department)
    
    elif current_user.role == UserRole.admin:
        query = query.join(CVSubmission.student).where(CVSubmission.status == CVStatus.approved)

    result = await db.execute(query)
    cvs = result.scalars().all()
    return [
        {
            **_serialize_cv(cv),
            "summary": 
            _build_summary(cv),
        }
        for cv in cvs
    ]


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
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.cv_id == cv_id)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        return None

    if current_user.role == UserRole.student and cv.student_id != current_user.id:
        return None

    if current_user.role == UserRole.advisor and cv.student and cv.student.department != current_user.department:
        return None

    return cv


async def update_cv(cv_id: str, data: dict[str, Any], current_user: User, db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.cv_id == cv_id, CVSubmission.student_id == current_user.id)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        return None

    cv.career_counseling = data.get("career_counseling", cv.career_counseling)
    cv.student_image_url = data.get("student_image", cv.student_image_url)
    cv.status = CVStatus.pending_advisor
    cv.rejection_comment = None
    _attach_cv_sections(cv, data)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to update CV cv_id=%s for student_id=%s", cv_id, current_user.id)
        raise
    await db.refresh(cv)

    refreshed = await get_cv(cv_id, current_user, db)
    return _serialize_cv(refreshed) if refreshed else None


async def delete_cv(cv_id: str, current_user: User, db: AsyncSession) -> bool:
    result = await db.execute(
        select(CVSubmission).where(CVSubmission.cv_id == cv_id, CVSubmission.student_id == current_user.id)
    )
    cv = result.scalar_one_or_none()
    if cv is None:
        return False

    await db.delete(cv)
    await db.commit()
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
        logger.exception("Failed to schedule PDF generation for approved cv_id=%s", cv_id)

    return {
        "cv_id": str(cv.cv_id),
        "status": cv.status.value,
        "message": "CV approved successfully",
    }


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

    student_email_result = await db.execute(
        select(User.email).where(User.id == cv.student_id)
    )
    student_email = student_email_result.scalar_one_or_none()

    if student_email:
        try:
            _schedule_rejection_email(student_email, comment)
        except Exception:
            logger.exception("Failed to schedule rejection email for cv_id=%s", cv_id)
    else:
        logger.warning("Student email not found for rejected cv_id=%s student_id=%s", cv_id, cv.student_id)

    return {
        "cv_id": str(cv.cv_id),
        "status": cv.status.value,
        "rejection_comment": cv.rejection_comment,
        "message": "CV rejected successfully",
    }
