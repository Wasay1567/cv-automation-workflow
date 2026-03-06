from clerk_backend_api import Clerk, AuthenticateRequestOptions
from fastapi import HTTPException
import os
from dotenv import load_dotenv

load_dotenv()

clerk_sdk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))

def authenticate_user(request):
    try:
        request_state = clerk_sdk.authenticate_request(
            request, 
            AuthenticateRequestOptions(authorized_parties=["http://localhost:8080"], jwt_key=os.getenv("JWT_KEY"))
        )
        if not request_state.is_signed_in:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = request_state.payload.get("sub")
        return {"user_id": user_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))