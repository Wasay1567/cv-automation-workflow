from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin import (
	get_pending_advisors as get_pending_advisors_service,
	approve_advisor as approve_advisor_service,
	reject_advisor as reject_advisor_service,
	notify_students_without_cv as notify_students_without_cv_service,
	upsert_form_deadline as upsert_form_deadline_service,
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


async def notify_students_without_cv(subject: str, body: str, deadline, db: AsyncSession):
	return await notify_students_without_cv_service(subject, body, deadline, db)


async def upsert_form_deadline(deadline_timestamp: int, db: AsyncSession):
	return await upsert_form_deadline_service(deadline_timestamp, db)
