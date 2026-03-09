import os
from dotenv import load_dotenv

load_dotenv()

PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

print("Loaded PARENT_FOLDER_ID:", PARENT_FOLDER_ID)