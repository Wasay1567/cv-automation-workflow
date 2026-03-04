from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin import (
	get_pending_advisors as get_pending_advisors_service,
	approve_advisor as approve_advisor_service,
	reject_advisor as reject_advisor_service,
)


async def get_pending_advisors(db: AsyncSession):
	return await get_pending_advisors_service(db)


async def approve_advisor(advisor_id: str, db: AsyncSession):
	result = await approve_advisor_service(advisor_id, db)
	if result is None:
		raise HTTPException(status_code=404, detail="Advisor not found or already processed")
	return result


async def reject_advisor(advisor_id: str, db: AsyncSession):
	result = await reject_advisor_service(advisor_id, db)
	if result is None:
		raise HTTPException(status_code=404, detail="Advisor not found or already processed")
	return result
