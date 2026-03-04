from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.users import sync_user_preferences as sync_user_preferences_controller
from middlewares.admin import get_current_user
from database import get_db
from models import User


class SyncUserRequest(BaseModel):
    department: str = Field(..., min_length=1, max_length=150)
    role: Literal["student", "advisor"]

router = APIRouter(
    prefix="/",
    tags=["User"],
    dependencies=[Depends(get_current_user)],  # applies to all routes in this router
)


@router.post("/user/sync")
async def sync_user_data(
    req: SyncUserRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await sync_user_preferences_controller(
        db=db,
        clerk_user_id=user.clerk_user_id,
        department=req.department,
        role=req.role,
    )


