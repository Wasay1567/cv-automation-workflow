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

    @staticmethod
    def send_cv_rejection_email(to_email: str, student_name: str, rejection_comment: str | None = None):
        comment_html = (
            f"<p><strong>Reviewer comments:</strong> {rejection_comment}</p>"
            if rejection_comment
            else ""
        )

        return resend.Emails.send({
            "from": "Acme <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "CV Submission Rejected",
            "html": f"""
                <h2>Hello {student_name},</h2>
                <p>Your CV submission has been reviewed and marked as rejected.</p>
                {comment_html}
                <p>Please update your submission and try again.</p>
                <br/>
                <p>Regards,<br/>NED University CV Portal</p>
            """,
        })