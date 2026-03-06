from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import cv_controller
from app.database import get_db
from app.middlewares.admin import get_current_user
from app.models import User

router = APIRouter(prefix="/cv-submissions", tags=["CV"])


class CVCreateRequest(BaseModel):
    class PersonalInfoPayload(BaseModel):
        name: Optional[str] = None
        father_name: Optional[str] = None
        department: Optional[str] = None
        batch: Optional[str] = None
        cell: Optional[str] = None
        roll_no: Optional[str] = None
        cnic: Optional[str] = None
        email: Optional[str] = None
        gender: Optional[str] = None
        dob: Optional[date] = None
        address: Optional[str] = None

    class AcademicPayload(BaseModel):
        degree: Optional[str] = None
        university: Optional[str] = None
        year: Optional[str] = None
        gpa: Optional[str] = None
        majors: Optional[str] = None

    class InternshipPayload(BaseModel):
        organization: Optional[str] = None
        position: Optional[str] = None
        field: Optional[str] = None
        from_date: Optional[date] = None
        to_date: Optional[date] = None

    class IndustrialVisitPayload(BaseModel):
        organization: Optional[str] = None
        purpose: Optional[str] = None
        visit_date: Optional[str] = None

    class FYPPayload(BaseModel):
        title: Optional[str] = None
        company: Optional[str] = None
        objectives: Optional[str] = None

    class CertificatePayload(BaseModel):
        name: Optional[str] = None

    class AchievementPayload(BaseModel):
        description: Optional[str] = None

    class SkillPayload(BaseModel):
        name: Optional[str] = None

    class ExtraCurricularPayload(BaseModel):
        activity: Optional[str] = None

    class ReferencePayload(BaseModel):
        name: Optional[str] = None
        contact: Optional[str] = None
        occupation: Optional[str] = None
        relation: Optional[str] = None

    career_counseling: bool = False
    personal_info: Optional[PersonalInfoPayload] = None
    academics: list[AcademicPayload] = Field(default_factory=list)
    internships: list[InternshipPayload] = Field(default_factory=list)
    industrial_visits: list[IndustrialVisitPayload] = Field(default_factory=list)
    fyp: Optional[FYPPayload] = None
    certificates: list[CertificatePayload] = Field(default_factory=list)
    achievements: list[AchievementPayload] = Field(default_factory=list)
    skills: list[SkillPayload] = Field(default_factory=list)
    extra_curricular: list[ExtraCurricularPayload] = Field(default_factory=list)
    references: list[ReferencePayload] = Field(default_factory=list)


class CVRejectRequest(BaseModel):
    comments: Optional[str] = None


@router.post("/", status_code=201)
async def create_cv(
    payload: CVCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_create_cv(payload.model_dump(), user, db)


@router.get("/")
async def list_cvs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_list_cvs(user, db)


@router.get("/me")
async def get_my_cvs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_get_student_cvs(user, db)


@router.get("/{cv_id}")
async def get_cv(
    cv_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_get_cv(cv_id, user, db)


@router.put("/{cv_id}")
async def update_cv(
    cv_id: str,
    payload: CVCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_update_cv(cv_id, payload.model_dump(), user, db)


@router.delete("/{cv_id}")
async def delete_cv(
    cv_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_delete_cv(cv_id, user, db)


@router.post("/{cv_id}/approve")
async def approve_cv(
    cv_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_approve_cv(cv_id, user, db)


@router.post("/{cv_id}/reject")
async def reject_cv(
    cv_id: str,
    payload: CVRejectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_reject_cv(cv_id, payload.comments, user, db)
