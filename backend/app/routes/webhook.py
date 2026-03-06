import os
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from database import get_db
from models import User, UserRole, UserStatus

router = APIRouter()

CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET")
UNIVERSITY_EMAIL_DOMAIN = "@cloud.neduet.edu.pk"


def is_university_email(email: str) -> bool:
    return email.lower().endswith(UNIVERSITY_EMAIL_DOMAIN)


@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):

    if not CLERK_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="CLERK_WEBHOOK_SECRET is not configured")

    payload = await request.body()
    headers = request.headers

    # Verify webhook signature
    try:
        wh = Webhook(CLERK_WEBHOOK_SECRET)
        event = wh.verify(payload, headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event.get("data", {})

    clerk_user_id = data.get("id")
    if not clerk_user_id:
        raise HTTPException(status_code=400, detail="Missing Clerk user id in webhook payload")

    # ============================
    # USER CREATED
    # ============================

    if event_type == "user.created":

        email_addresses = data.get("email_addresses", [])
        email = (
            email_addresses[0].get("email_address")
            if email_addresses and isinstance(email_addresses[0], dict)
            else None
        )
        if not email:
            raise HTTPException(status_code=400, detail="Missing user email in user.created payload")

        # Get role from metadata (set during signup)
        public_metadata = data.get("public_metadata", {})
        requested_role = public_metadata.get("role", "student")

        if requested_role not in ["student", "advisor"]:
            requested_role = "student"

        role = UserRole(requested_role)

        # Advisor must be approved
        if role == UserRole.advisor:
            status = UserStatus.inactive
        else:
            status = UserStatus.active

        if not is_university_email(email):
            return {
                "status": "ignored",
                "reason": "invalid_email_domain",
                "detail": f"Only '{UNIVERSITY_EMAIL_DOMAIN}' emails are allowed",
            }

        existing_result = await db.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        existing_user = existing_result.scalar_one_or_none()
        print(existing_user)

        if existing_user:
            existing_user.email = email
            existing_user.role = role
            existing_user.status = status
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail="User data violates database constraints")
            return {"status": "success", "message": "User already existed and was updated"}

        user = User(
            clerk_user_id=clerk_user_id,
            email=email,
            role=role,
            status=status,
        )

        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(status_code=409, detail="User data violates database constraints")
        print(f"Created user {email} with role {role.value} and status {status.value}")

    # ============================
    # USER UPDATED
    # ============================

    elif event_type == "user.updated":

        email_addresses = data.get("email_addresses", [])
        email = (
            email_addresses[0].get("email_address")
            if email_addresses and isinstance(email_addresses[0], dict)
            else None
        )
        if not email:
            raise HTTPException(status_code=400, detail="Missing user email in user.updated payload")

        result = await db.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            if not is_university_email(email):
                return {
                    "status": "ignored",
                    "reason": "invalid_email_domain",
                    "detail": f"Only '{UNIVERSITY_EMAIL_DOMAIN}' emails are allowed",
                }
            user.email = email
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail="User data violates database constraints")

    # ============================
    # USER DELETED
    # ============================

    elif event_type == "user.deleted":

        result = await db.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.status = UserStatus.inactive
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                raise HTTPException(status_code=409, detail="User data violates database constraints")

    else:
        return {
            "status": "ignored",
            "reason": "unsupported_event_type",
            "event_type": event_type,
        }

    return {"status": "success"}