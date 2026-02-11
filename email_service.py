import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import config

logger = logging.getLogger(__name__)

class EmailService:
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    def __init__(self, gmail_user: Optional[str] = None, gmail_password: Optional[str] = None):
        self.gmail_user = gmail_user or config.GMAIL_USER
        self.gmail_password = gmail_password or config.GMAIL_APP_PASSWORD
        self.enabled = self.gmail_user is not None and self.gmail_password is not None

    def send_email(self, to: str, subject: str, body: str, html: bool = False) -> bool:
        if not self.enabled:
            logger.info(f"Gmail disabled - would send to {to}: {subject}")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.gmail_user
            msg['To'] = to
            msg['Subject'] = subject

            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.gmail_user, self.gmail_password)
                server.send_message(msg)

            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

email_service = EmailService()
