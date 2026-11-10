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


def get_settings() -> Settings:
    """Read the settings from the environment each time they are needed."""
    # SUPABASE_SERVICE_ROLE_KEY is the older name for the private server key.
    supabase_key = (
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    return Settings(
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_key=supabase_key.strip(),
        auth_secret=os.getenv("AUTH_SECRET", "").strip(),
        cors_origins=origins or ["*"],
    )
