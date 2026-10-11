"""Google login helpers shared by the Calendar and Gmail tools."""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import DATA_DIR

TOKEN_FILE = DATA_DIR / "token.json"
CLIENT_SECRET_FILE = DATA_DIR / "credentials.json"

# Calendar: read + create events. Gmail: read mail + create drafts.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def get_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    if not creds or not creds.valid:
        raise RuntimeError("Google is not authorized. Run authorize_google.py first.")
    return creds


def calendar_service():
    return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)


def gmail_service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)
