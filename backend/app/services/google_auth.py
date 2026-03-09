import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# This calculates the path to the 'backend' folder
# __file__ is backend/app/services/google_auth.py
# .parent.parent.parent goes up 3 levels to 'backend/'
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CLIENT_SECRETS_PATH = BASE_DIR / "client_secrets.json"
TOKEN_PATH = BASE_DIR / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/presentations"
]

def get_credentials():
    creds = None
    
    # 1. Check if we already logged in previously
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    # 2. If no valid token, we need to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # This looks for the file you downloaded from GCP
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_PATH), SCOPES
            )
            # This will trigger the browser popup
            creds = flow.run_local_server(port=0)
        
        # 3. Save the token for next time
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
            
    return creds

# Initialize the services using YOUR personal account
credentials = get_credentials()
drive_service = build("drive", "v3", credentials=credentials)