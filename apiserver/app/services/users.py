from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole, UserStatus


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
