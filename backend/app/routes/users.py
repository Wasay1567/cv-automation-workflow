from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.users import sync_user_preferences as sync_user_preferences_controller
from middlewares.admin import get_current_auth
from database import get_db


class SyncUserRequest(BaseModel):
    department: str = Field(..., min_length=1, max_length=150)
    role: Literal["student", "advisor"]

router = APIRouter(
    prefix="",
    tags=["User"],
)


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


