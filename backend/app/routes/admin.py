from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from controllers.admin import (
    get_pending_advisors as get_pending_advisors_controller,
    approve_advisor as approve_advisor_controller,
    reject_advisor as reject_advisor_controller,
)
from middlewares.admin import require_active_admin
from database import get_db

router = APIRouter(
    prefix="/cv/admin",
    tags=["Admin"],
    dependencies=[Depends(require_active_admin)],  # applies to all routes in this router
)

@router.get("/advisors/pending")
async def get_pending_advisors(db: AsyncSession = Depends(get_db)):
    return await get_pending_advisors_controller(db)

@router.post("/advisors/{advisor_id}/approve")
async def approve_advisor(advisor_id: str, db: AsyncSession = Depends(get_db)):
    return await approve_advisor_controller(advisor_id, db)


@router.post("/advisors/{advisor_id}/reject")
async def reject_advisor(advisor_id: str, db: AsyncSession = Depends(get_db)):
    return await reject_advisor_controller(advisor_id, db)
