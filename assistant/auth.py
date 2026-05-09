"""Google OAuth 2.0 credential management for Calendar and Gmail.

Credentials are loaded lazily — no auth flow runs at import time, so a missing
credentials.json will not crash the assistant on startup.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_TOKEN_PATH = Path("token.pickle")
_CREDENTIALS_PATH = Path(os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json"))


def get_google_credentials():
    """Return valid Google OAuth2 credentials, refreshing or re-authorizing as needed."""
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if _TOKEN_PATH.exists():
        with _TOKEN_PATH.open("rb") as fh:
            creds = pickle.load(fh)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Google token refreshed successfully")
            except Exception as exc:
                logger.warning("Token refresh failed (%s) — re-running OAuth flow", exc)
                creds = None

        if not creds:
            if not _CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Google credentials not found at '{_CREDENTIALS_PATH}'. "
                    "Download OAuth client JSON from Google Cloud Console and set "
                    "GOOGLE_CREDENTIALS_FILE in your .env file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(_CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("OAuth2 flow completed — new token issued")

        with _TOKEN_PATH.open("wb") as fh:
            pickle.dump(creds, fh)

    return creds


def get_calendar_service():
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=get_google_credentials())


def get_gmail_service():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=get_google_credentials())
