from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Mapping

from app.backend.core.config import get_settings

logger = logging.getLogger(__name__)


def _send_message(message: EmailMessage) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            password = (
                settings.smtp_password.get_secret_value()
                if settings.smtp_password
                else ""
            )
            server.login(settings.smtp_username, password)
        server.send_message(message)


def send_early_access_emails(application: Mapping[str, str]) -> None:
    """Send optional notifications after the database transaction has committed."""

    settings = get_settings()
    if not settings.email_notifications_enabled:
        logger.info(
            "Email notifications are not configured; the application was stored."
        )
        return

    sender = str(settings.smtp_from_email)
    applicant_email = application["work_email"]

    internal = EmailMessage()
    internal["Subject"] = "New Call-Off early-access application"
    internal["From"] = sender
    internal["To"] = str(settings.early_access_notification_email)
    internal.set_content(
        "A new early-access application has been received.\n\n"
        f"Name: {application['full_name']}\n"
        f"Email: {applicant_email}\n"
        f"Company: {application['company_name']}\n"
        f"Job title: {application['job_title']}\n"
        f"Trade: {application['subcontractor_type']}\n"
        f"Company size: {application['company_size']}\n"
        f"Active projects: {application['active_projects']}\n"
        f"Interest: {application['interest_level']}\n"
    )

    confirmation = EmailMessage()
    confirmation["Subject"] = "Call-Off early-access application received"
    confirmation["From"] = sender
    confirmation["To"] = applicant_email
    confirmation.set_content(
        f"Hello {application['full_name']},\n\n"
        "Thank you for your interest in Call-Off. We have received your "
        "early-access application and will review it before contacting you "
        "about any suitable opportunities.\n\n"
        f"Questions can be sent to {settings.public_contact_email}.\n"
    )

    for message, message_type in (
        (internal, "internal"),
        (confirmation, "applicant"),
    ):
        try:
            _send_message(message)
        except (OSError, smtplib.SMTPException):
            logger.warning(
                "The %s application email could not be delivered.",
                message_type,
            )
