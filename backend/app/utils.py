from clerk_backend_api import Clerk, AuthenticateRequestOptions
from fastapi import HTTPException
import os
from dotenv import load_dotenv

load_dotenv()

clerk_sdk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))


def _get_authorized_parties() -> list[str]:
    configured = os.getenv("CLERK_AUTHORIZED_PARTIES", "")
    parties = [party.strip() for party in configured.split(",") if party.strip()]
    return parties or ["http://localhost:8080", "http://127.0.0.1:8080"]


def authenticate_user(request):
    try:
        request_state = clerk_sdk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=_get_authorized_parties(),
                jwt_key=os.getenv("JWT_KEY"),
            ),
        )
        if not request_state.is_signed_in:
            raise HTTPException(status_code=401, detail="Invalid token")

        user_id = request_state.payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing user id")

        return {"user_id": user_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")