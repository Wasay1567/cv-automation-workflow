from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, UserRole, UserStatus
from utils import authenticate_user


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth = authenticate_user(request)
    clerk_user_id = auth["user_id"]

    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    return user


async def require_active_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    if user.status != UserStatus.active:
        raise HTTPException(status_code=403, detail="Admin account is not active")

    return user