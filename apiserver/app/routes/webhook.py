import os
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.database import get_db
from app.models import User, UserRole, UserStatus


router = APIRouter()

CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET")
UNIVERSITY_EMAIL_DOMAIN = "@cloud.neduet.edu.pk"


def is_university_email(email: str) -> bool:
    return email.lower().endswith(UNIVERSITY_EMAIL_DOMAIN)


@router.post("/webhooks/clerk")
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # ============================
    # CHECK WEBHOOK SECRET
    # ============================

    if not CLERK_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="CLERK_WEBHOOK_SECRET is not configured",
        )

    # ============================
    # READ RAW REQUEST
    # ============================

    payload = await request.body()

    # Normalize header names
    headers = {
        key.lower(): value
        for key, value in request.headers.items()
    }

    # ============================
    # VERIFY WEBHOOK
    # ============================

    svix_id = headers.get("svix-id")
    svix_timestamp = headers.get("svix-timestamp")
    svix_signature = headers.get("svix-signature")

    if not all([svix_id, svix_timestamp, svix_signature]):
        print("ERROR: Missing required Svix headers")

        raise HTTPException(
            status_code=400,
            detail="Missing required Svix headers",
        )

    try:
        wh = Webhook(CLERK_WEBHOOK_SECRET)
        wh.verify(payload, headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload")

    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid or empty webhook payload")

    event_type = event.get("type")

    if not event_type:
        raise HTTPException(
            status_code=400,
            detail="Missing event type in payload",
        )

    data = event.get("data", {})

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook data",
        )

    clerk_user_id = data.get("id")

    if not clerk_user_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Clerk user id in webhook payload",
        )

    # ============================
    # USER CREATED
    # ============================

    if event_type == "user.created":

        email_addresses = data.get("email_addresses", [])

        email = (
            email_addresses[0].get("email_address")
            if email_addresses
            and isinstance(email_addresses[0], dict)
            else None
        )

        if not email:
            raise HTTPException(
                status_code=400,
                detail="Missing user email in user.created payload",
            )

        # Get role from Clerk public metadata
        public_metadata = data.get("public_metadata", {})

        if not isinstance(public_metadata, dict):
            public_metadata = {}

        requested_role = public_metadata.get("role", "student")

        if requested_role not in ["student", "advisor"]:
            requested_role = "student"

        role = UserRole(requested_role)

        # Advisors start inactive and require approval
        if role == UserRole.advisor:
            status = UserStatus.inactive
        else:
            status = UserStatus.active

        # University email restriction
        if not is_university_email(email):
            return {
                "status": "ignored",
                "reason": "invalid_email_domain",
                "detail": (
                    f"Only '{UNIVERSITY_EMAIL_DOMAIN}' emails are allowed"
                ),
            }

        # Check whether user already exists
        existing_result = await db.execute(
            select(User).where(
                User.clerk_user_id == clerk_user_id
            )
        )

        existing_user = existing_result.scalar_one_or_none()

        if existing_user:

            existing_user.email = email
            existing_user.role = role
            existing_user.status = status

            try:
                await db.commit()

            except IntegrityError:
                await db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="User data violates database constraints",
                )

            return {
                "status": "success",
                "message": "User already existed and was updated",
            }

        # Create new user
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

            duplicate_result = await db.execute(
                select(User).where(
                    or_(
                        User.clerk_user_id == clerk_user_id,
                        User.email == email,
                    )
                )
            )
            duplicate_user = duplicate_result.scalars().first()

            if duplicate_user and duplicate_user.clerk_user_id == clerk_user_id:
                return {
                    "status": "success",
                    "message": "Duplicate webhook delivery already processed",
                }

            raise HTTPException(
                status_code=409,
                detail="User data violates database constraints",
            )

    # ============================
    # USER UPDATED
    # ============================

    elif event_type == "user.updated":

        email_addresses = data.get("email_addresses", [])

        email = (
            email_addresses[0].get("email_address")
            if email_addresses
            and isinstance(email_addresses[0], dict)
            else None
        )

        if not email:
            raise HTTPException(
                status_code=400,
                detail="Missing user email in user.updated payload",
            )

        result = await db.execute(
            select(User).where(
                User.clerk_user_id == clerk_user_id
            )
        )

        user = result.scalar_one_or_none()

        if user:

            if not is_university_email(email):
                return {
                    "status": "ignored",
                    "reason": "invalid_email_domain",
                    "detail": (
                        f"Only '{UNIVERSITY_EMAIL_DOMAIN}' emails are allowed"
                    ),
                }

            user.email = email

            try:
                await db.commit()

            except IntegrityError:
                await db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="User data violates database constraints",
                )

    # ============================
    # USER DELETED
    # ============================

    elif event_type == "user.deleted":

        result = await db.execute(
            select(User).where(
                User.clerk_user_id == clerk_user_id
            )
        )

        user = result.scalar_one_or_none()

        if user:

            user.status = UserStatus.inactive

            try:
                await db.commit()

            except IntegrityError:
                await db.rollback()

                raise HTTPException(
                    status_code=409,
                    detail="User data violates database constraints",
                )

    # ============================
    # UNSUPPORTED EVENT
    # ============================

    else:

        return {
            "status": "ignored",
            "reason": "unsupported_event_type",
            "event_type": event_type,
        }

    return {
        "status": "success",
    }
