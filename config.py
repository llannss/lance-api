"""Application settings.

Every secret is read from an environment variable. Locally the values come
from a .env file that Git ignores. On Vercel they come from the project's
Environment Variables page.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Reads a local .env file if one exists. It does nothing on Vercel.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    auth_secret: str
    cors_origins: list[str]
    # Public address of the website, used in emailed links
    # (e.g. https://gpu-finder.vercel.app). No trailing slash.
    site_url: str
    # Gmail account that sends verification and reset emails, and its
    # 16-character App Password (Google Account > Security > App passwords).
    gmail_address: str
    gmail_app_password: str
    gemini_api_key: str
    gemini_model: str


def get_settings() -> Settings:
    """Read the settings from the environment each time they are needed."""
    # SUPABASE_SERVICE_ROLE_KEY is the older name for the private server key.
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )
    # The website reaches the API through its own /api rewrite (same origin),
    # so no other origin needs access by default. List origins here only for
    # other browser clients that call the API directly.
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=supabase_key.strip(),
        auth_secret=os.getenv("AUTH_SECRET", "").strip(),
        cors_origins=origins,
        site_url=os.getenv("SITE_URL", "").strip().rstrip("/"),
        gmail_address=os.getenv("GMAIL_ADDRESS", "").strip(),
        # Google shows App Passwords with spaces; they work without them.
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip(),
    )
