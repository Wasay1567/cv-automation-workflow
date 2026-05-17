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
from urllib.parse import quote, unquote, urlparse

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
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
IMAGE_FALLBACK = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

logger = logging.getLogger(__name__)


def _ensure_windows_proactor_policy() -> None:
    if sys.platform != "win32":
        return

    policy = asyncio.get_event_loop_policy()
    if policy.__class__.__name__ == "WindowsSelectorEventLoopPolicy":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())



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
        logger.exception("[PDF_SERVICE] Failed to download profile image from URL: %s", url)
        return IMAGE_FALLBACK


def _extract_s3_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    key = unquote(parsed.path).lstrip("/")
    if not key:
        return ""

    bucket_prefix = f"{AWS_S3_BUCKET_NAME or ''}/"
    if bucket_prefix and key.startswith(bucket_prefix):
        key = key[len(bucket_prefix):]

    return key.strip().strip("/")


def _normalize_s3_reference(reference: str) -> str:
    clean_reference = reference.strip().strip("/")
    if clean_reference.startswith("s3://"):
        clean_reference = clean_reference[5:]
        if "/" in clean_reference:
            clean_reference = clean_reference.split("/", 1)[1]
        else:
            clean_reference = ""
    return clean_reference.strip().strip("/")


def _list_image_keys_by_prefix(s3_client, prefix: str) -> list[str]:
    image_keys: list[str] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=AWS_S3_BUCKET_NAME, Prefix=prefix):
        keys = [item["Key"] for item in page.get("Contents", []) if item.get("Key") and not item["Key"].endswith("/")]
        image_keys.extend([key for key in keys if Path(key).suffix.lower() in IMAGE_EXTENSIONS])
    logger.info("[PDF_SERVICE] S3 image lookup completed | Prefix: %s | Matches: %d", prefix, len(image_keys))
    return image_keys


def _fetch_profile_image_from_s3(student_id: str) -> str:
    if not AWS_S3_BUCKET_NAME:
        logger.info("[PDF_SERVICE] Profile image lookup skipped | AWS bucket not configured | Student: %s", student_id)
        return ""

    try:
        s3_client = _get_s3_client()
    except Exception:
        logger.exception("[PDF_SERVICE] Failed to initialize S3 client for profile image lookup | Student: %s", student_id)
        return ""

    clean_id = str(student_id).strip().strip("/")
    if clean_id:
        if clean_id.startswith(f"{PROFILE_PHOTO_PREFIX}/"):
            prefixes = [clean_id.rstrip("/")]
        else:
            prefixes = [f"{PROFILE_PHOTO_PREFIX}/{clean_id}"]
    else:
        logger.info("[PDF_SERVICE] Profile image lookup skipped | Empty student id")
        return ""

    tried_prefixes: set[str] = set()
    try:
        for base_prefix in prefixes:
            if not base_prefix or base_prefix in tried_prefixes:
                continue
            tried_prefixes.add(base_prefix)

            logger.info("[PDF_SERVICE] Looking up profile image in S3 | Student: %s | Prefix: %s", clean_id, base_prefix)

            image_keys = _list_image_keys_by_prefix(s3_client, base_prefix)
            if not image_keys:
                image_keys = _list_image_keys_by_prefix(s3_client, f"{base_prefix}/")
            if not image_keys:
                logger.info("[PDF_SERVICE] No profile image found for student | Student: %s | Prefix: %s", clean_id, base_prefix)
                continue

            # Exactly one image is expected per student id; pick deterministic first item if duplicates exist.
            key = sorted(image_keys)[0]
            response = s3_client.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=key)
            logger.info(
                "[PDF_SERVICE] Profile image resolved from S3 | Student: %s | Key: %s | Content-Type: %s",
                clean_id,
                key,
                response.get("ContentType") or "unknown",
            )
            return _image_bytes_to_data_uri(response["Body"].read(), response.get("ContentType"), key)
    except (ClientError, BotoCoreError, Exception):
        logger.exception("[PDF_SERVICE] Profile image lookup failed | Student: %s", clean_id)
        return ""

    logger.info("[PDF_SERVICE] Profile image not found in S3 | Student: %s", clean_id)
    return ""


def resolve_profile_image(profile_image_url: str | None, student_id: str | None = None) -> str:
    normalized = str(profile_image_url or "").strip()
    logger.info(
        "[PDF_SERVICE] Resolving profile image | Student: %s | Has provided URL: %s",
        student_id or "unknown",
        bool(normalized),
    )

    if not normalized:
        return _fetch_profile_image_from_s3(student_id or "") if student_id else ""

    if normalized.startswith("data:"):
        logger.info("[PDF_SERVICE] Using provided profile image data URI | Student: %s", student_id or "unknown")
        return normalized

    if normalized.startswith(("http://", "https://")):
        s3_key = _extract_s3_key_from_url(normalized)
        if s3_key and s3_key.startswith(f"{PROFILE_PHOTO_PREFIX}/"):
            logger.info(
                "[PDF_SERVICE] Profile image URL maps to S3 key | Student: %s | Key: %s",
                student_id or "unknown",
                s3_key,
            )
            try:
                s3_client = _get_s3_client()
                response = s3_client.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=s3_key)
                logger.info(
                    "[PDF_SERVICE] Profile image loaded from S3 URL key | Student: %s | Key: %s | Content-Type: %s",
                    student_id or "unknown",
                    s3_key,
                    response.get("ContentType") or "unknown",
                )
                return _image_bytes_to_data_uri(response["Body"].read(), response.get("ContentType"), s3_key)
            except Exception:
                logger.exception(
                    "[PDF_SERVICE] Failed to load profile image from S3 URL key; falling back to HTTP download | Student: %s | Key: %s",
                    student_id or "unknown",
                    s3_key,
                )

        logger.info("[PDF_SERVICE] Downloading profile image from URL | Student: %s | URL: %s", student_id or "unknown", normalized)
        return _download_image_as_data_uri(normalized)

    if student_id:
        resolved_from_s3 = _fetch_profile_image_from_s3(student_id)
        if resolved_from_s3:
            return resolved_from_s3

    logger.info(
        "[PDF_SERVICE] Falling back to provided profile image value | Student: %s | Value: %s",
        student_id or "unknown",
        normalized,
    )

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
        "profile_image_url": resolve_profile_image(data.get("profile_image_url"), data.get("student_id")),
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

