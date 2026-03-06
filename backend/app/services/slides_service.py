from app.services.google_auth import slides_service


def replace_placeholders(presentation_id: str, name: str, email: str):

    requests = [
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{name}}",
                    "matchCase": True
                },
                "replaceText": name
            }
        },
        {
            "replaceAllText": {
                "containsText": {
                    "text": "{{email}}",
                    "matchCase": True
                },
                "replaceText": email
            }
        }
    ]

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests}
    ).execute()