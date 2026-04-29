from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote
from typing import Any
import asyncio
import sys

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright
import requests
import base64

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR.parent / "templates"
TEMPLATE_NAME = "cv_template.html"
OUTPUT_FILE = BASE_DIR / "sample_cv.pdf"


def _ensure_windows_proactor_policy() -> None:
    """Playwright needs subprocess support, which requires Proactor loop on Windows."""
    if sys.platform != "win32":
        return

    policy = asyncio.get_event_loop_policy()
    if policy.__class__.__name__ == "WindowsSelectorEventLoopPolicy":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


SAMPLE_DATA = {
    "student_id": "SAMPLE-0001",
    "name": "Abdul Wasay Soomro",
    "profession": "Devops Engineer",
    "phone": "+123-456-7890",
    "email": "test@example.com",
    "address": "123 Anywhere Street., Any City",
    "about_me": (
        "Experienced DevOps Engineer with a strong background in cloud infrastructure, automation, and continuous integration. Skilled in designing and implementing scalable solutions to optimize development workflows and enhance system reliability."
    ),
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
            "description": [
                "create more than 100 graphic designs for big companies",
                "complete a lot of complicated work",
            ],
        },
        {
            "date": "(2017 – 2019)",
            "title": "Senior Graphic Designer",
            "company": "Iarana, inc",
            "description": [
                "create more than 100 graphic designs for big companies",
                "complete a lot of complicated work",
            ],
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

def get_profile_image_base64(drive_url: str) -> str:
    """Converts a public Google Drive sharing URL into a Base64 string."""
    try:
        # Check if it's a standard Freepik or already processed URL
        if "://google.com" not in drive_url:
            return drive_url
            
        if "/d/" in drive_url:
            file_id = drive_url.split("/d/")[1].split("/")[0]
        else:
            raise ValueError("Invalid Google Drive URL format")

        direct_download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        response = requests.get(direct_download_url, timeout=10)
        response.raise_for_status()

        image_bytes = response.content
        base64_encoded = base64.b64encode(image_bytes).decode("utf-8")
        content_type = response.headers.get("Content-Type", "image/png")

        return f"data:{content_type};base64,{base64_encoded}"

    except Exception as e:
        print(f"Error processing image: {e}")
        # Return fallback 1x1 transparent pixel
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="




def _build_template_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize inbound CV payload to the template's expected shape."""
    experience = []
    for item in data.get("experience", []):
        from_date = (item.get("from_date") or "").strip()
        to_date = (item.get("to_date") or "").strip()
        date = item.get("date") or f"({from_date} - {to_date})".strip()

        raw_description = item.get("description", [])
        if isinstance(raw_description, list):
            description = [str(x).strip() for x in raw_description if str(x).strip()]
        else:
            text = str(raw_description).strip()
            description = [text] if text else []

        experience.append(
            {
                "date": date,
                "title": item.get("title", ""),
                "company": item.get("company", ""),
                "description": description,
            }
        )

    education = []
    for item in data.get("education", []):
        from_date = (item.get("from_date") or "").strip()
        to_date = (item.get("to_date") or "").strip()
        date = item.get("date") or f"({from_date} - {to_date})".strip()

        description = item.get("description")
        if description is None:
            description = item.get("majors", "")

        education.append(
            {
                "date": date,
                "degree": item.get("degree", ""),
                "institution": item.get("institution", ""),
                "description": str(description),
            }
        )

    if data.get("profile_image_url"):
        data["profile_image_url"] = get_profile_image_base64(data["profile_image_url"])

    payload = {
        "student_id": data.get("student_id", ""),
        "name": data.get("name", ""),
        "profession": data.get("profession", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "about_me": data.get("about_me", ""),
        "profile_image_url": data.get("profile_image_url", ""),
        "skills": data.get("skills") or [],
        "languages": data.get("languages") or [],
        "certificates": data.get("certificates") or [],
        "personality_score": data.get("personality_score"),
        "experience": experience,
        "education": education,
    }
    return payload


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
            page.pdf(
                path=str(output_file),
                format="Letter",
                print_background=True,
                margin={"top": "0in", "right": "0in", "bottom": "0in", "left": "0in"},
            )
            browser.close()
    finally:
        temp_html_path.unlink(missing_ok=True)

    return output_file


def render_pdf() -> Path:
    _ensure_windows_proactor_policy()
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template(TEMPLATE_NAME)
    html_content = template.render(SAMPLE_DATA)

    # Render via Chromium so modern CSS in the template matches browser output.
    with NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as temp_html:
        temp_html.write(html_content)
        temp_html_path = Path(temp_html.name)

    file_url = f"file:///{quote(str(temp_html_path).replace('\\', '/'))}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.goto(file_url, wait_until="networkidle")
            page.pdf(
                path=str(OUTPUT_FILE),
                format="Letter",
                print_background=True,
                margin={"top": "0in", "right": "0in", "bottom": "0in", "left": "0in"},
            )
            browser.close()
    finally:
        temp_html_path.unlink(missing_ok=True)

    return OUTPUT_FILE


def render_sample_pdf() -> Path:
    return render_pdf_from_data(SAMPLE_DATA, OUTPUT_FILE)
