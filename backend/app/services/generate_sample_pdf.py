import logging
from pathlib import Path
from functools import lru_cache
import asyncio
import base64
import logging
import mimetypes
import sys
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
import requests

from app.core.config import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_S3_BUCKET_NAME, AWS_SECRET_ACCESS_KEY

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR.parent / "templates"
TEMPLATE_NAME = "cv_template.html"
OUTPUT_FILE = BASE_DIR / "sample_cv.pdf"
PROFILE_PHOTO_PREFIX = "profile-photo"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
IMAGE_FALLBACK = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

logger = logging.getLogger(__name__)


def _ensure_windows_proactor_policy() -> None:
    if sys.platform != "win32":
        return

    policy = asyncio.get_event_loop_policy()
    if policy.__class__.__name__ == "WindowsSelectorEventLoopPolicy":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


SAMPLE_DATA = {
    "student_id": "SAMPLE-0001",
    "name": "Abdul Wasay Soomro",
    "profession": "DevOps Engineer",
    "phone": "+123-456-7890",
    "email": "test@example.com",
    "address": "123 Anywhere Street, Any City",
    "about_me": "Experienced DevOps Engineer with a strong background in cloud infrastructure, automation, and continuous integration.",
    "profile_image_url": "https://img.freepik.com/free-photo/portrait-white-man-isolated_53876-40306.jpg?semt=ais_hybrid&w=740&q=80",
    "skills": [
        {"name": "Web Design", "level": 5},
        {"name": "Branding", "level": 4},
        {"name": "Graphic Design", "level": 5},
        {"name": "SEO", "level": 4},
        {"name": "Marketing", "level": 3},
    ],
    "languages": [
        {"name": "English", "percent": 95},
        {"name": "French", "percent": 70},
    ],
    "certificates": [
        "AWS Certified DevOps Engineer - Professional",
        "Docker and Kubernetes Administration",
        "Google Cloud Professional Cloud Architect",
    ],
    "personality_score": 8,
    "experience": [
        {
            "date": "(2020 –2023)",
            "title": "Senior Graphic Designer",
            "company": "Fauget studio",
            "description": ["create more than 100 graphic designs for big companies", "complete a lot of complicated work"],
        },
        {
            "date": "(2017 – 2019)",
            "title": "Senior Graphic Designer",
            "company": "Iarana, inc",
            "description": ["create more than 100 graphic designs for big companies", "complete a lot of complicated work"],
        },
    ],
    "education": [
        {
            "date": "(August 2024- Present)",
            "degree": "Bachelor of Software Engineering",
            "institution": "NED UNIVERSITY",
            "description": "3.5",
        }
    ],
}


@lru_cache(maxsize=1)
def _get_s3_client():
    session_kwargs: dict[str, str] = {"region_name": AWS_REGION}
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        session_kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        session_kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **session_kwargs)


def _image_bytes_to_data_uri(image_bytes: bytes, content_type: str | None, key: str) -> str:
    resolved_content_type = content_type or mimetypes.guess_type(key)[0] or "image/png"
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{resolved_content_type};base64,{encoded}"


def _download_image_as_data_uri(url: str) -> str:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return _image_bytes_to_data_uri(response.content, response.headers.get("Content-Type"), url)
    except Exception:
        return IMAGE_FALLBACK


def _s3_image_keys(cv_id: str) -> list[str]:
    clean_id = str(cv_id).strip().strip("/")
    if not clean_id:
        return []

    if clean_id.startswith(f"{PROFILE_PHOTO_PREFIX}/"):
        base_key = clean_id
        file_name = Path(clean_id).name
        folder_prefix = clean_id if clean_id.endswith("/") else f"{clean_id}/"
    else:
        base_key = f"{PROFILE_PHOTO_PREFIX}/{clean_id}"
        file_name = clean_id
        folder_prefix = f"{PROFILE_PHOTO_PREFIX}/{clean_id}/"

    candidates = [base_key]
    for extension in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        candidates.append(f"{base_key}{extension}")
    candidates.append(f"{PROFILE_PHOTO_PREFIX}/{file_name}.jpg")
    candidates.append(f"{PROFILE_PHOTO_PREFIX}/{file_name}.jpeg")
    candidates.append(f"{PROFILE_PHOTO_PREFIX}/{file_name}.png")
    candidates.append(f"{PROFILE_PHOTO_PREFIX}/{file_name}.webp")
    candidates.append(f"{PROFILE_PHOTO_PREFIX}/{file_name}.gif")
    candidates.append(folder_prefix)
    return list(dict.fromkeys(candidates))


def _fetch_profile_image_from_s3(cv_id: str) -> str:
    if not AWS_S3_BUCKET_NAME:
        return ""

    try:
        s3_client = _get_s3_client()
    except Exception:
        return ""

    for key in _s3_image_keys(cv_id):
        try:
            response = s3_client.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=key)
            return _image_bytes_to_data_uri(response["Body"].read(), response.get("ContentType"), key)
        except ClientError:
            continue
        except (BotoCoreError, Exception):
            continue

    prefix = f"{PROFILE_PHOTO_PREFIX}/{str(cv_id).strip().strip('/')}/"
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=AWS_S3_BUCKET_NAME, Prefix=prefix):
            keys = [item["Key"] for item in page.get("Contents", []) if item.get("Key") and not item["Key"].endswith("/")]
            image_keys = [key for key in keys if Path(key).suffix.lower() in IMAGE_EXTENSIONS]
            if not image_keys:
                continue
            key = sorted(image_keys, key=lambda item: (0 if Path(item).name.lower().startswith("profile") else 1, item))[0]
            response = s3_client.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=key)
            return _image_bytes_to_data_uri(response["Body"].read(), response.get("ContentType"), key)
    except (ClientError, BotoCoreError, Exception):
        return ""

    return ""


def resolve_profile_image(profile_image_url: str | None, cv_id: str | None = None) -> str:
    normalized = str(profile_image_url or "").strip()
    if not normalized:
        return _fetch_profile_image_from_s3(cv_id or "") if cv_id else ""

    if normalized.startswith("data:"):
        return normalized

    if normalized.startswith(("http://", "https://")):
        return _download_image_as_data_uri(normalized)

    return normalized


def _build_template_payload(data: dict[str, Any]) -> dict[str, Any]:
    def normalize_entries(items: list[dict[str, Any]], keys: tuple[str, str, str]) -> list[dict[str, Any]]:
        normalized_items: list[dict[str, Any]] = []
        for item in items:
            from_date = str(item.get("from_date") or "").strip()
            to_date = str(item.get("to_date") or "").strip()
            date = item.get("date") or f"({from_date} - {to_date})".strip()
            description = item.get(keys[2]) if item.get(keys[2]) is not None else ""
            if isinstance(description, list):
                description = [str(value).strip() for value in description if str(value).strip()]
            else:
                description = str(description).strip()
            normalized_items.append(
                {
                    "date": date,
                    keys[0]: item.get(keys[0], ""),
                    keys[1]: item.get(keys[1], ""),
                    keys[2]: description,
                }
            )
        return normalized_items

    experience = normalize_entries(data.get("experience", []), ("title", "company", "description"))
    education = []
    for item in data.get("education", []):
        from_date = str(item.get("from_date") or "").strip()
        to_date = str(item.get("to_date") or "").strip()
        date = item.get("date") or f"({from_date} - {to_date})".strip()
        description = item.get("description") if item.get("description") is not None else item.get("majors", "")
        education.append(
            {
                "date": date,
                "degree": item.get("degree", ""),
                "institution": item.get("institution", ""),
                "description": str(description),
            }
        )

    return {
        "student_id": data.get("student_id", ""),
        "name": data.get("name", ""),
        "profession": data.get("profession", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "about_me": data.get("about_me", ""),
        "profile_image_url": resolve_profile_image(data.get("profile_image_url"), data.get("cv_id") or data.get("student_id")),
        "skills": data.get("skills") or [],
        "languages": data.get("languages") or [],
        "certificates": data.get("certificates") or [],
        "personality_score": data.get("personality_score"),
        "experience": experience,
        "education": education,
    }


def render_pdf_from_data(data: dict[str, Any], output_file: Path) -> Path:
    _ensure_windows_proactor_policy()
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template(TEMPLATE_NAME)
    html_content = template.render(_build_template_payload(data))

    with NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as temp_html:
        temp_html.write(html_content)
        temp_html_path = Path(temp_html.name)

    file_url = f"file:///{quote(str(temp_html_path).replace('\\', '/'))}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.goto(file_url, wait_until="networkidle")
            page.pdf(path=str(output_file), format="Letter", print_background=True, margin={"top": "0in", "right": "0in", "bottom": "0in", "left": "0in"})
            browser.close()
    finally:
        temp_html_path.unlink(missing_ok=True)

    return output_file


def render_sample_pdf() -> Path:
    return render_pdf_from_data(SAMPLE_DATA, OUTPUT_FILE)
