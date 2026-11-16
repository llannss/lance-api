"""Sends account emails (verify address, reset password) through Gmail.

Gmail needs an App Password, not the account's normal password. Turn on
2-Step Verification, then create one at https://myaccount.google.com/apppasswords
(the page isn't linked from Google's security menus).
Put the address in GMAIL_ADDRESS and the 16-character password in
GMAIL_APP_PASSWORD. Gmail allows roughly 500 messages a day on a free account.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage

from config import get_settings

logger = logging.getLogger("gpu_api.mailer")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_TIMEOUT_SECONDS = 15


class EmailNotConfiguredError(Exception):
    """GMAIL_ADDRESS, GMAIL_APP_PASSWORD or SITE_URL is missing."""


def is_configured() -> bool:
    settings = get_settings()
    return bool(settings.gmail_address and settings.gmail_app_password and settings.site_url)


def send_email(to: str, subject: str, text: str) -> None:
    """Send a plain-text email. Raises on failure; callers decide what to do."""
    settings = get_settings()
    if not is_configured():
        raise EmailNotConfiguredError()

    message = EmailMessage()
    message["From"] = f"GPU Finder <{settings.gmail_address}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)

    with smtplib.SMTP_SSL(
        SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS,
        context=ssl.create_default_context(),
    ) as smtp:
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.send_message(message)


def site_link(page: str, secret: str) -> str:
    return f"{get_settings().site_url}/{page}?token={secret}"


def send_verification_email(to: str, secret: str) -> None:
    link = site_link("verify.html", secret)
    send_email(
        to,
        "Confirm your GPU Finder account",
        "Welcome to GPU Finder!\n\n"
        "Confirm your email address to finish creating your account:\n"
        f"{link}\n\n"
        "This link works once and expires in 24 hours.\n"
        "If you didn't sign up, you can ignore this email.",
    )


def send_password_reset_email(to: str, secret: str) -> None:
    link = site_link("reset.html", secret)
    send_email(
        to,
        "Reset your GPU Finder password",
        "Someone asked to reset the password for this GPU Finder account.\n\n"
        "Choose a new password here:\n"
        f"{link}\n\n"
        "This link works once and expires in 30 minutes.\n"
        "If you didn't ask for this, ignore this email; your password stays the same.",
    )
