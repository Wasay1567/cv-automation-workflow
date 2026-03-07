from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.users import sync_user_preferences as sync_user_preferences_controller
from app.middlewares.admin import get_current_auth, get_current_user
from app.database import get_db
from app.models import User


class SyncUserRequest(BaseModel):
    department: str = Field(..., min_length=1, max_length=150)
    role: Literal["student", "advisor"]

router = APIRouter(
    prefix="",
    tags=["User"],
)


@router.get("/profiles")
async def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "clerk_user_id": user.clerk_user_id,
        "department": user.department,
        "role": user.role.value,
        "status": user.status.value,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/user/sync")
async def sync_user_data(
    req: SyncUserRequest,
    db: AsyncSession = Depends(get_db),
    auth: dict[str, str] = Depends(get_current_auth),
):
    return await sync_user_preferences_controller(
        db=db,
        clerk_user_id=auth["user_id"],
        department=req.department,
        role=req.role,
    )


