from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.database import AsyncSessionLocal
from app.models import User, CVSubmission

router = APIRouter(prefix="/info", tags=["Student Info"])


# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


@router.get("/{student_id}")
async def get_student_full_info(
    student_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete student information including
    all CV submissions and related sections.
    """

    query = (
        select(User)
        .where(User.id == student_id)
        .options(
            selectinload(User.cvs)
            .selectinload(CVSubmission.personal_info),
            
            selectinload(User.cvs)
            .selectinload(CVSubmission.academics),

            selectinload(User.cvs)
            .selectinload(CVSubmission.internships),

            selectinload(User.cvs)
            .selectinload(CVSubmission.industrial_visits),

            selectinload(User.cvs)
            .selectinload(CVSubmission.certificates),

            selectinload(User.cvs)
            .selectinload(CVSubmission.achievements),

            selectinload(User.cvs)
            .selectinload(CVSubmission.skills),

            selectinload(User.cvs)
            .selectinload(CVSubmission.extra_curricular),

            selectinload(User.cvs)
            .selectinload(CVSubmission.references),
        )
    )

    result = await db.execute(query)
    student = result.scalars().first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return student