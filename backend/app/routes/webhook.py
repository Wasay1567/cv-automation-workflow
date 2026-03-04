import os
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from svix.webhooks import Webhook, WebhookVerificationError

from app.database import get_db
from app.models import User, UserRole, UserStatus

router = APIRouter()

CLERK_WEBHOOK_SECRET = os.getenv("CLERK_WEBHOOK_SECRET")


@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request, db: Session = Depends(get_db)):

    payload = await request.body()
    headers = request.headers

    # Verify webhook signature
    try:
        wh = Webhook(CLERK_WEBHOOK_SECRET)
        event = wh.verify(payload, headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]

    clerk_user_id = data["id"]
    email = data["email_addresses"][0]["email_address"]

    # ============================
    # USER CREATED
    # ============================

    if event_type == "user.created":

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

        user = User(
            clerk_user_id=clerk_user_id,
            email=email,
            role=role,
            status=status
        )

        db.add(user)
        db.commit()

    # ============================
    # USER UPDATED
    # ============================

    elif event_type == "user.updated":

        user = db.query(User).filter(
            User.clerk_user_id == clerk_user_id
        ).first()

        if user:
            user.email = email
            db.commit()

    # ============================
    # USER DELETED
    # ============================

    elif event_type == "user.deleted":

        user = db.query(User).filter(
            User.clerk_user_id == clerk_user_id
        ).first()

        if user:
            user.status = UserStatus.inactive
            db.commit()

    return {"status": "success"}