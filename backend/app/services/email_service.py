import os
import resend
from typing import List

resend.api_key = os.getenv("RESEND_API_KEY")


class EmailService:

    @staticmethod
    async def send_advisor_approval_email(to_email: str, advisor_name: str):
        return resend.Emails.send({
            "from": "Acme <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "🎉 Advisor Approval Notification",
            "html": f"""
                <h2>Congratulations {advisor_name}!</h2>
                <p>Your advisor account has been approved by the admin.</p>
                <p>You can now log in and access the advisor dashboard.</p>
                <br/>
                <p>Regards,<br/>NED University CV Portal</p>
            """
        })

    @staticmethod
    async def send_bulk_email(to_emails: List[str], subject: str, html: str):
        return resend.Emails.send({
            "from": "Acme <onboarding@resend.dev>",
            "to": to_emails,
            "subject": subject,
            "html": html
        })