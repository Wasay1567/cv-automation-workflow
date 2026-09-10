from __future__ import annotations

import argparse
import json
import re

from app.services.generate_sample_pdf import resolve_profile_image
from app.services.pdf_service import generate_and_upload_cv


def build_sample_payload(cv_id: str, name: str, profile_image_url: str = "") -> dict:
    return {
        "student_id": cv_id,
        "cv_id": cv_id,
        "name": name,
        "profession": "DevOps Engineer",
        "phone": "+123-456-7890",
        "email": "test@example.com",
        "address": "123 Anywhere Street, Any City",
        "about_me": (
            "Experienced DevOps Engineer with a strong background in cloud infrastructure, automation, "
            "and continuous integration."
        ),
        "profile_image_url": profile_image_url,
        "skills": [
            {"name": "AWS", "level": 5},
            {"name": "Docker", "level": 5},
            {"name": "Kubernetes", "level": 4},
            {"name": "Terraform", "level": 4},
            {"name": "Python", "level": 4},
        ],
        "languages": [
            {"name": "English", "percent": 95},
            {"name": "Urdu", "percent": 85},
        ],
        "certificates": [
            "AWS Certified DevOps Engineer - Professional",
            "Docker and Kubernetes Administration",
        ],
        "personality_score": 8,
        "experience": [
            {
                "date": "(2022 - Present)",
                "title": "Senior DevOps Engineer",
                "company": "Acme Cloud",
                "description": [
                    "Built CI/CD pipelines for multiple production services",
                    "Automated cloud infrastructure provisioning and monitoring",
                ],
            },
            {
                "date": "(2020 - 2022)",
                "title": "Cloud Engineer",
                "company": "ByteWorks",
                "description": [
                    "Managed container orchestration on Kubernetes",
                    "Improved deployment reliability and rollback speed",
                ],
            },
        ],
        "education": [
            {
                "date": "(2016 - 2020)",
                "degree": "Bachelor of Software Engineering",
                "institution": "NED University",
                "description": "CGPA 3.5",
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local end-to-end CV generation smoke test.")
    parser.add_argument("--cv-id", default="CV-LOCAL-001", help="CV / student id used for S3 lookup and PDF naming")
    parser.add_argument("--name", default="Abdul Wasay Soomro", help="Display name to put on the CV")
    parser.add_argument(
        "--profile-image-url",
        default="",
        help="Optional profile image URL; leave blank to fetch from S3 profile-photo/<cv-id>/",
    )
    parser.add_argument(
        "--debug-image",
        action="store_true",
        help="Print the resolved image prefix and payload size before generation",
    )
    args = parser.parse_args()

    payload = build_sample_payload(args.cv_id, args.name, args.profile_image_url)
    print("Using payload:\n" + json.dumps(payload, indent=2))

    if args.debug_image:
        resolved = resolve_profile_image(payload.get("profile_image_url"), payload.get("student_id"))
        prefix = resolved[:40]
        data_uri_match = re.match(r"^data:([^;]+);base64,", resolved)
        print(
            "Resolved profile image:\n"
            f"  starts_with_data_uri: {resolved.startswith('data:')}\n"
            f"  media_type: {data_uri_match.group(1) if data_uri_match else 'n/a'}\n"
            f"  length: {len(resolved)}\n"
            f"  preview: {prefix}"
        )

    result = generate_and_upload_cv(payload)
    print("\nGeneration complete:\n" + json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())