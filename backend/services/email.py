"""Password-reset email delivery. SMTP credentials remain server-side only."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from backend.config import EMAIL_DEV_LOG_LINKS, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME, SMTP_USE_TLS

logger = logging.getLogger(__name__)


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    """Deliver a reset link, or log it locally when SMTP is intentionally absent."""
    if not SMTP_HOST:
        if EMAIL_DEV_LOG_LINKS:
            logger.warning("Development password reset link for %s: %s", recipient, reset_url)
        else:
            logger.info("Password reset email suppressed because SMTP is not configured")
        return

    message = EmailMessage()
    message["Subject"] = "Reset your LifeLane password"
    message["From"] = SMTP_FROM or SMTP_USERNAME
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your LifeLane account.\n\n"
        f"Reset your password: {reset_url}\n\n"
        "This link expires in 15 minutes and can be used once. If you did not request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as client:
            if SMTP_USE_TLS:
                client.starttls()
            if SMTP_USERNAME:
                client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Unable to send LifeLane password-reset email")
