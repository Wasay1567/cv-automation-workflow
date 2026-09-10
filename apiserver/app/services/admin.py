from datetime import date
from html import escape

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.email_service import EmailService
from fastapi.concurrency import run_in_threadpool
from app.models import CVStatus, CVSubmission, User, UserRole, UserStatus

async def get_pending_advisors(db: AsyncSession):
    result = await db.execute(
        select(User.id, User.email, User.department, User.created_at).where(
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
            "created_at": created_at if created_at else None,
        }
        for advisor_id, email, department, created_at in advisors
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
    await run_in_threadpool(
        EmailService.send_advisor_approval_email,
        advisor.email,
        advisor.email.split("@")[0]
    )
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


async def notify_students_without_cv(subject: str, body: str, deadline: date, db: AsyncSession):
    submitted_cv_exists = (
        select(CVSubmission.cv_id)
        .where(
            CVSubmission.student_id == User.id,
            CVSubmission.status.in_(
                [
                    CVStatus.submitted,
                    CVStatus.pending_advisor,
                    CVStatus.approved,
                    CVStatus.rejected,
                ]
            ),
        )
        .exists()
    )

    result = await db.execute(
        select(User.email).where(
            User.role == UserRole.student,
            User.status == UserStatus.active,
            ~submitted_cv_exists,
        )
    )

    recipient_emails = result.scalars().all()
    if not recipient_emails:
        return {
            "message": "No students found without submitted CVs",
            "notified_count": 0,
            "deadline": deadline.isoformat(),
        }

    safe_body = escape(body).replace("\n", "<br/>")
    html = (
        f"<p>{safe_body}</p>"
        f"<p><strong>Submission deadline:</strong> {deadline.isoformat()}</p>"
    )

    await run_in_threadpool(
        EmailService.send_bulk_email,
        recipient_emails,
        subject,
        html,
    )

    return {
        "message": "Reminder email sent successfully",
        "notified_count": len(recipient_emails),
        "deadline": deadline.isoformat(),
    }
