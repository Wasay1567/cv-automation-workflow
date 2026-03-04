from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, UserRole, UserStatus

async def get_pending_advisors(db: AsyncSession):
    result = await db.execute(
        select(User.id, User.email, User.department).where(
            User.role == UserRole.advisor,
            User.status == UserStatus.inactive,
        )
    )
    advisors = result.all()
    return [
        {
            "id": advisor_id,
            "email": email,
            "department": department,
        }
        for advisor_id, email, department in advisors
    ]

async def approve_advisor(advisor_id: str, db: AsyncSession):
    result = await db.execute(
        select(User).where(
            User.id == advisor_id,
            User.role == UserRole.advisor,
            User.status == UserStatus.inactive,
        )
    )
    advisor = result.scalar_one_or_none()

    if not advisor:
        return None

    advisor.status = UserStatus.active
    await db.commit()
    return {"message": "Advisor approved successfully"}

async def reject_advisor(advisor_id: str, db: AsyncSession):
    result = await db.execute(
        select(User).where(
            User.id == advisor_id,
            User.role == UserRole.advisor,
            User.status == UserStatus.inactive,
        )
    )
    advisor = result.scalar_one_or_none()

    if not advisor:
        return None

    advisor.status = UserStatus.rejected
    await db.commit()
    return {"message": "Advisor rejected successfully"}
