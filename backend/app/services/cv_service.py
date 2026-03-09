from datetime import date, datetime
import asyncio
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

    # Prevent unhandled task exceptions from being silently ignored.
    task.add_done_callback(lambda t: t.exception())


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
                "year": academic.year,
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
                "visit_date": visit.visit_date,
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
    personal_info = data.get("personal_info")
    cv.personal_info = PersonalInfo(**personal_info) if personal_info else None

    cv.academics = [Academic(**item) for item in data.get("academics", [])]
    cv.internships = [Internship(**item) for item in data.get("internships", [])]
    cv.industrial_visits = [IndustrialVisit(**item) for item in data.get("industrial_visits", [])]
    cv.fyp = FYP(**data["fyp"]) if data.get("fyp") else None
    cv.certificates = [Certificate(name=cert_name) for cert_name in data.get("certificates", [])]
    cv.achievements = [Achievement(description=achievement_desc) for achievement_desc in data.get("achievements", [])]
    cv.skills = [Skill(name=skill_name) for skill_name in data.get("skills", [])]
    cv.extra_curricular = [ExtraCurricular(activity=activity) for activity in data.get("extra_curricular", [])]
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
    cv = CVSubmission(
        student_id=current_user.id,
        status=CVStatus.pending_advisor,
        student_image_url=data.get("student_image"),
        career_counseling=data.get("career_counseling", False),
    )
    _attach_cv_sections(cv, data)

    db.add(cv)
    await db.commit()

    result = await db.execute(
        select(CVSubmission)
        .options(*_cv_load_options())
        .where(CVSubmission.cv_id == cv.cv_id)
    )
    return _serialize_cv(result.scalar_one())


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

    await db.commit()
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
    await db.commit()

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
    await db.commit()

    student_email_result = await db.execute(
        select(User.email).where(User.id == cv.student_id)
    )
    student_email = student_email_result.scalar_one_or_none()

    if student_email:
        _schedule_rejection_email(student_email, comment)

    return {
        "cv_id": str(cv.cv_id),
        "status": cv.status.value,
        "rejection_comment": cv.rejection_comment,
        "message": "CV rejected successfully",
    }
