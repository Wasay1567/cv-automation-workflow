from clerk_backend_api import Clerk, AuthenticateRequestOptions
from fastapi import HTTPException
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError

load_dotenv()

clerk_sdk = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

def upload_to_s3(file_obj, bucket, s3_path):
    try:
        s3_client.upload_fileobj(file_obj, bucket, s3_path)
        return f"https://{bucket}.s3.amazonaws.com/{s3_path}"
    except NoCredentialsError:
        return None


def _get_authorized_parties() -> list[str]:
    configured = os.getenv("CLERK_AUTHORIZED_PARTIES", "")
    return [party.strip() for party in configured.split(",") if party.strip()]


def _build_auth_options() -> AuthenticateRequestOptions:
    options: dict = {}

    jwt_key = os.getenv("JWT_KEY")
    if jwt_key:
        options["jwt_key"] = jwt_key

    authorized_parties = _get_authorized_parties()
    if authorized_parties:
        options["authorized_parties"] = authorized_parties

    return AuthenticateRequestOptions(**options)


def authenticate_user(request):
    try:
        request_state = clerk_sdk.authenticate_request(
            request,
            _build_auth_options(),
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