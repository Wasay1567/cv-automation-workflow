from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.users import sync_user_preferences as sync_user_preferences_service
from app.services.users import get_form_deadline as get_form_deadline_service


async def sync_user_preferences(
    db: AsyncSession,
    clerk_user_id: str,
    department: str,
    role: str,
):
    result = await sync_user_preferences_service(
        db=db,
        clerk_user_id=clerk_user_id,
        department=department,
        role=role,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")

    return result


async def get_form_deadline(db: AsyncSession):
    return await get_form_deadline_service(db)
