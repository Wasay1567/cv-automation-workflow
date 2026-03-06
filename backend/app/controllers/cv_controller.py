from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, UserRole, UserStatus
from services import cv_service


def _ensure_student(user: User) -> None:
    if user.role != UserRole.student:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can perform this action")


def _ensure_admin_or_advisor(user: User) -> None:
    if user.role not in [UserRole.admin, UserRole.advisor]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only advisors and admins can perform this action")

    if user.role == UserRole.advisor and user.status != UserStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Advisor account is not active")


async def handle_create_cv(data: dict, current_user: User, db: AsyncSession) -> dict:
    _ensure_student(current_user)
    return await cv_service.create_cv(data, current_user, db)


async def handle_get_cv(cv_id: str, current_user: User, db: AsyncSession) -> dict:
    cv = await cv_service.get_cv(cv_id, current_user, db)
    if cv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return cv_service.serialize_cv(cv)


async def handle_list_cvs(current_user: User, db: AsyncSession) -> list:
    _ensure_admin_or_advisor(current_user)
    return await cv_service.list_cvs(current_user, db)


async def handle_get_student_cvs(current_user: User, db: AsyncSession) -> list:
    _ensure_student(current_user)
    return await cv_service.get_student_cvs(current_user, db)


async def handle_update_cv(cv_id: str, data: dict, current_user: User, db: AsyncSession) -> dict:
    _ensure_student(current_user)
    updated = await cv_service.update_cv(cv_id, data, current_user, db)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return updated


async def handle_delete_cv(cv_id: str, current_user: User, db: AsyncSession) -> dict:
    _ensure_student(current_user)
    deleted = await cv_service.delete_cv(cv_id, current_user, db)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return {"message": f"CV '{cv_id}' deleted successfully"}


async def handle_approve_cv(cv_id: str, current_user: User, db: AsyncSession) -> dict:
    _ensure_admin_or_advisor(current_user)
    approved = await cv_service.approve_cv(cv_id, current_user, db)
    if approved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return approved


async def handle_reject_cv(cv_id: str, comment: str | None, current_user: User, db: AsyncSession) -> dict:
    _ensure_admin_or_advisor(current_user)
    rejected = await cv_service.reject_cv(cv_id, comment, current_user, db)
    if rejected is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return rejected
