import json
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import cv_controller
from app.database import get_db
from app.middlewares.admin import get_current_user
from app.models import User

router = APIRouter(prefix="/cv-submissions", tags=["CV"])


class CVCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class PersonalInfoPayload(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        name: Optional[str] = None
        father_name: Optional[str] = Field(
            default=None,
            validation_alias=AliasChoices("father_name", "fatherName"),
        )
        department: Optional[str] = None
        batch: Optional[str] = None
        cell: Optional[str] = None
        roll_no: Optional[str] = Field(
            default=None,
            validation_alias=AliasChoices("roll_no", "rollNo"),
        )
        cnic: Optional[str] = None
        email: Optional[str] = None
        gender: Optional[str] = None
        dob: Optional[date] = None
        address: Optional[str] = None

    class AcademicPayload(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        degree: Optional[str] = None
        university: Optional[str] = None
        gpa: Optional[str] = None
        majors: Optional[str] = None
        from_date: Optional[date] = Field(
            default=None,
            validation_alias=AliasChoices("from_date", "from"),
        )
        to_date: Optional[date] = Field(
            default=None,
            validation_alias=AliasChoices("to_date", "to"),
        )

        @field_validator("from_date", "to_date", mode="before")
        @classmethod
        def _parse_optional_dates(cls, value):
            if value in (None, ""):
                return None
            if isinstance(value, str):
                raw = value.strip()
                for fmt in ("%Y-%m-%d", "%b, %Y", "%B, %Y", "%b %Y", "%B %Y"):
                    try:
                        return datetime.strptime(raw, fmt).date()
                    except ValueError:
                        continue
            return value
        

    class InternshipPayload(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        organization: Optional[str] = None
        position: Optional[str] = None
        field: Optional[str] = None
        duties: list[str] = Field(default_factory=list)
        from_date: Optional[date] = Field(
            default=None,
            validation_alias=AliasChoices("from_date", "from"),
        )
        to_date: Optional[date] = Field(
            default=None,
            validation_alias=AliasChoices("to_date", "to"),
        )

        @field_validator("from_date", "to_date", mode="before")
        @classmethod
        def _parse_optional_dates(cls, value):
            if value in (None, ""):
                return None
            if isinstance(value, str):
                raw = value.strip()
                for fmt in ("%Y-%m-%d", "%b, %Y", "%B, %Y", "%b %Y", "%B %Y"):
                    try:
                        return datetime.strptime(raw, fmt).date()
                    except ValueError:
                        continue
            return value

    class IndustrialVisitPayload(BaseModel):
        model_config = ConfigDict(populate_by_name=True)

        organization: Optional[str] = None
        purpose: Optional[str] = None
        visit_date: Optional[date] = Field(
            default=None,
            validation_alias=AliasChoices("visit_date", "date"),
        )

        @field_validator("visit_date", mode="before")
        @classmethod
        def _parse_optional_visit_date(cls, value):
            if value in (None, ""):
                return None
            if isinstance(value, str):
                raw = value.strip()
                for fmt in ("%Y-%m-%d", "%b, %Y", "%B, %Y", "%b %Y", "%B %Y"):
                    try:
                        return datetime.strptime(raw, fmt).date()
                    except ValueError:
                        continue
            return value

    class FYPPayload(BaseModel):
        title: Optional[str] = None
        company: Optional[str] = None
        objectives: Optional[str] = None

    # class CertificatePayload(BaseModel):
    #     name: Optional[str] = None

    # class AchievementPayload(BaseModel):
    #     description: Optional[str] = None

    # class SkillPayload(BaseModel):
    #     name: Optional[str] = None

    # class ExtraCurricularPayload(BaseModel):
    #     activity: Optional[str] = None

    class ReferencePayload(BaseModel):
        name: Optional[str] = None
        contact: Optional[str] = None
        occupation: Optional[str] = None
        relation: Optional[str] = None

    career_counseling: bool = Field(
        default=False,
        validation_alias=AliasChoices("career_counseling", "careerCounseling"),
    )
    student_image: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("student_image", "studentImage", "student_image_url", "studentImageUrl"),
    )
    personal_info: Optional[PersonalInfoPayload] = Field(
        default=None,
        validation_alias=AliasChoices("personal_info", "personalInfo"),
    )
    academics: list[AcademicPayload] = Field(default_factory=list)
    internships: list[InternshipPayload] = Field(default_factory=list)
    industrial_visits: list[IndustrialVisitPayload] = Field(
        default_factory=list,
        validation_alias=AliasChoices("industrial_visits", "industrialVisits"),
    )
    fyp: Optional[FYPPayload] = None
    certificates: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    extra_curricular: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("extra_curricular", "extraCurricular"),
    )
    assessment: list[int] = Field(default_factory=list)
    references: list[ReferencePayload] = Field(default_factory=list)


class CVRejectRequest(BaseModel):
    comments: Optional[str] = None


class CVDownloadRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    student_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("student_ids", "cv_ids"),
    )


async def _parse_cv_request(request: Request) -> tuple[dict[str, Any], UploadFile | None]:
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        image_file: UploadFile | None = None

        for key in ("student_image", "studentImage", "student_image_file", "studentImageFile"):
            candidate = form.get(key)
            if hasattr(candidate, "filename") and hasattr(candidate, "read"):
                image_file = candidate
                break

        payload_raw = form.get("payload") or form.get("data") or form.get("cv")
        if isinstance(payload_raw, str) and payload_raw.strip():
            try:
                return json.loads(payload_raw), image_file
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON payload: {exc.msg}",
                ) from exc

        payload: dict[str, Any] = {}
        for key, value in form.multi_items():
            if key in {"payload", "data", "cv", "student_image", "studentImage", "student_image_file", "studentImageFile"}:
                continue
            if isinstance(value, str):
                payload[key] = value

        return payload, image_file

    return await request.json(), None


@router.post("/", status_code=201)
async def create_cv(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload_data, image_file = await _parse_cv_request(request)
    payload = CVCreateRequest.model_validate(payload_data)
    return await cv_controller.handle_create_cv(payload.model_dump(), user, db, image_file)


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
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload_data, image_file = await _parse_cv_request(request)
    payload = CVCreateRequest.model_validate(payload_data)
    return await cv_controller.handle_update_cv(cv_id, payload.model_dump(), user, db, image_file)


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


@router.post("/download-cv")
async def download_cv(
    request: Request,
    payload: CVDownloadRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cv_controller.handle_download_cvs(payload.student_ids, user, db, request)
