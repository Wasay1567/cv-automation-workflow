from datetime import date, datetime, timezone
from html import escape

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.email_service import EmailService
from fastapi.concurrency import run_in_threadpool
from app.models import CVStatus, CVSubmission, SysVar, User, UserRole, UserStatus

CV_SUBMISSION_DEADLINE_KEY = "cv_submission_deadline"

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


async def set_cv_submission_deadline(deadline: datetime, db: AsyncSession):
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    deadline = deadline.astimezone(timezone.utc)

    result = await db.execute(
        select(SysVar).where(SysVar.key == CV_SUBMISSION_DEADLINE_KEY)
    )
    sys_var = result.scalar_one_or_none()

    if sys_var is None:
        sys_var = SysVar(
            key=CV_SUBMISSION_DEADLINE_KEY,
            value=deadline.isoformat(),
            description="Deadline for creating or updating CV submissions",
        )
        db.add(sys_var)
    else:
        sys_var.value = deadline.isoformat()

    await db.commit()

    notification = await notify_students_without_cv(
        subject="CV Submission Deadline Updated",
        body=(
            "The CV submission deadline has been set or updated. "
            "Please submit your CV before the deadline."
        ),
        deadline=deadline,
        db=db,
    )

    return {
        "key": CV_SUBMISSION_DEADLINE_KEY,
        "deadline": deadline.isoformat(),
        "notified_count": notification["notified_count"],
        "message": "CV submission deadline saved successfully",
    }


async def get_cv_submission_deadline(db: AsyncSession):
    result = await db.execute(
        select(SysVar.value).where(SysVar.key == CV_SUBMISSION_DEADLINE_KEY)
    )
    deadline = result.scalar_one_or_none()

    return {
        "key": CV_SUBMISSION_DEADLINE_KEY,
        "deadline": deadline,
        "configured": deadline is not None,
    }
