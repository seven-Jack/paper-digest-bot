"""Email Sender - Send HTML emails via SMTP (Gmail compatible)."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email(subject: str, html_body: str, recipient: str):
    """Send an HTML email via SMTP."""
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    sender_email = os.environ.get("EMAIL_ADDRESS", "")
    sender_password = os.environ.get("EMAIL_PASSWORD", "")

    if not sender_email or not sender_password:
        raise ValueError("EMAIL_ADDRESS and EMAIL_PASSWORD must be set.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Paper Digest Bot <{sender_email}>"
    msg["To"] = recipient
    msg.attach(MIMEText(f"{subject}\n\nView in HTML client.", "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient], msg.as_string())

    logger.info(f"Email sent to {recipient}")
