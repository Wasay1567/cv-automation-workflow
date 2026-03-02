from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from app.controllers import cv_controller

router = APIRouter(prefix="/cv", tags=["CV"])


class CVCreateRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[list[str]] = Field(default_factory=list)
    experience: Optional[list[dict]] = Field(default_factory=list)
    education: Optional[list[dict]] = Field(default_factory=list)


@router.post("/", status_code=201)
def create_cv(payload: CVCreateRequest):
    return cv_controller.handle_create_cv(payload.model_dump())


@router.get("/")
def list_cvs():
    return cv_controller.handle_list_cvs()


@router.get("/{cv_id}")
def get_cv(cv_id: str):
    return cv_controller.handle_get_cv(cv_id)


@router.delete("/{cv_id}")
def delete_cv(cv_id: str):
    return cv_controller.handle_delete_cv(cv_id)
