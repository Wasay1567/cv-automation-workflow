@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):

    if not CLERK_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="CLERK_WEBHOOK_SECRET is not configured"
        )

    payload = await request.body()

    # Normalize headers for debugging + Svix
    headers = {k.lower(): v for k, v in request.headers.items()}

    # ============================
    # DEBUG
    # ============================

    print("\n========== CLERK WEBHOOK DEBUG ==========")
    print("Payload length:", len(payload))
    print("Svix ID:", headers.get("svix-id"))
    print("Svix timestamp:", headers.get("svix-timestamp"))
    print("Has Svix signature:", bool(headers.get("svix-signature")))
    print("Has webhook secret:", bool(CLERK_WEBHOOK_SECRET))
    print("Webhook secret prefix:",
          CLERK_WEBHOOK_SECRET[:6] if CLERK_WEBHOOK_SECRET else None)
    print("=========================================\n")

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
            detail="Missing required Svix headers"
        )

    try:
        wh = Webhook(CLERK_WEBHOOK_SECRET)

        event = wh.verify(payload, headers)

        print("SUCCESS: Webhook signature verified")
        print("Event type:", event.get("type") if isinstance(event, dict) else None)

    except WebhookVerificationError as e:

        print("\n========== WEBHOOK VERIFICATION FAILED ==========")
        print("Exception type:", type(e).__name__)
        print("Exception:", repr(e))
        print("==================================================\n")

        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature"
        )

    # ============================
    # VALIDATE EVENT
    # ============================

    if not event or not isinstance(event, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid or empty webhook payload"
        )

    event_type = event.get("type")

    if not event_type:
        raise HTTPException(
            status_code=400,
            detail="Missing event type in payload"
        )

    data = event.get("data", {})

    clerk_user_id = data.get("id")

    if not clerk_user_id:
        raise HTTPException(
            status_code=400,
            detail="Missing Clerk user id in webhook payload"
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
                detail="Missing user email in user.created payload"
            )

        public_metadata = data.get("public_metadata", {})

        requested_role = public_metadata.get("role", "student")

        if requested_role not in ["student", "advisor"]:
            requested_role = "student"

        role = UserRole(requested_role)

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
                    detail="User data violates database constraints"
                )

            return {
                "status": "success",
                "message": "User already existed and was updated"
            }

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
            raise HTTPException(
                status_code=409,
                detail="User data violates database constraints"
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
                detail="Missing user email in user.updated payload"
            )

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
                raise HTTPException(
                    status_code=409,
                    detail="User data violates database constraints"
                )

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
                raise HTTPException(
                    status_code=409,
                    detail="User data violates database constraints"
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

    return {"status": "success"}
