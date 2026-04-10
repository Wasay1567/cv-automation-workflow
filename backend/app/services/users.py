from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GloabalSettings, User, UserRole, UserStatus

FORM_DEADLINE_KEY = "form_deadline"


def _normalize_unix_timestamp(timestamp: int) -> int:
    return timestamp // 1000 if timestamp > 9999999999 else timestamp


async def sync_user_preferences(
    db: AsyncSession,
    clerk_user_id: str,
    department: str,
    role: str,
):
    print(clerk_user_id, department, role)
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        return None

    if role == UserRole.advisor.value:
        user.role = UserRole.advisor
        user.status = UserStatus.inactive
    else:
        user.role = UserRole.student
        user.status = UserStatus.active

    user.department = department

    await db.commit()
    await db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "department": user.department,
        "role": user.role.value,
        "status": user.status.value,
    }


async def get_form_deadline(db: AsyncSession):
    result = await db.execute(
        select(GloabalSettings.setting_value).where(GloabalSettings.setting_key == FORM_DEADLINE_KEY)
    )
    deadline_timestamp = result.scalar_one_or_none()

    if deadline_timestamp is None:
        return {"deadline": None}

    normalized_timestamp = _normalize_unix_timestamp(int(deadline_timestamp))

    return {
        "deadline": date.fromtimestamp(normalized_timestamp).isoformat()
    }
