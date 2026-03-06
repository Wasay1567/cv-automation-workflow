from fastapi import HTTPException, status
from app.services import cv_service


def handle_create_cv(data: dict) -> dict:
    return cv_service.create_cv(data)


def handle_get_cv(cv_id: str) -> dict:
    cv = cv_service.get_cv(cv_id)
    if cv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return cv


def handle_list_cvs() -> list:
    return cv_service.list_cvs()


def handle_delete_cv(cv_id: str) -> dict:
    deleted = cv_service.delete_cv(cv_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV with id '{cv_id}' not found",
        )
    return {"message": f"CV '{cv_id}' deleted successfully"}
