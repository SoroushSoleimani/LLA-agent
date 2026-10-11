"""Google Calendar and Gmail tools. Gmail is read + draft only (nothing is sent)."""

import base64
import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from config import TIMEZONE
from google_auth import calendar_service, gmail_service


# ---------- Calendar ----------

def list_events(days_ahead: int = 1) -> str:
    tz = ZoneInfo(TIMEZONE)
    start = datetime.datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=max(1, int(days_ahead)))
    items = (
        calendar_service()
        .events()
        .list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        )
        .execute()
        .get("items", [])
    )
    if not items:
        return "No events in this period."
    lines = []
    for e in items:
        when = e["start"].get("dateTime", e["start"].get("date"))
        until = e["end"].get("dateTime", e["end"].get("date"))
        lines.append(f"- {when} -> {until} | {e.get('summary', '(no title)')}")
    return "\n".join(lines)


def create_event(title: str, start: str, end: str, description: str = "") -> str:
    """start/end are ISO 8601, e.g. 2026-10-02T14:00:00."""
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start, "timeZone": TIMEZONE},
        "end": {"dateTime": end, "timeZone": TIMEZONE},
    }
    event = calendar_service().events().insert(calendarId="primary", body=body).execute()
    return f"Event created: {event.get('htmlLink')}"


# ---------- Gmail ----------

def read_inbox(max_results: int = 10, query: str = "is:unread in:inbox") -> str:
    svc = gmail_service()
    refs = (
        svc.users()
        .messages()
        .list(userId="me", q=query, maxResults=min(int(max_results), 25))
        .execute()
        .get("messages", [])
    )
    if not refs:
        return "No matching emails."
    lines = []
    for ref in refs:
        m = (
            svc.users()
            .messages()
            .get(userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        h = {x["name"]: x["value"] for x in m["payload"]["headers"]}
        lines.append(
            f"- id={ref['id']} | From: {h.get('From', '?')} | Subject: {h.get('Subject', '?')} "
            f"| Date: {h.get('Date', '?')} | Preview: {m.get('snippet', '')[:120]}"
        )
    return "\n".join(lines)


def _extract_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        text = _extract_text(part)
        if text:
            return text
    return ""


def read_email(message_id: str) -> str:
    m = gmail_service().users().messages().get(userId="me", id=message_id, format="full").execute()
    h = {x["name"]: x["value"] for x in m["payload"]["headers"]}
    body = _extract_text(m["payload"]) or m.get("snippet", "")
    return (
        f"From: {h.get('From', '?')}\nTo: {h.get('To', '?')}\n"
        f"Subject: {h.get('Subject', '?')}\nDate: {h.get('Date', '?')}\n\n{body[:4000]}"
    )


def create_draft(to: str, subject: str, body: str, reply_to_message_id: str = "") -> str:
    """Saves a draft in Gmail. It does NOT send anything."""
    svc = gmail_service()
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    message = {}
    if reply_to_message_id:
        orig = (
            svc.users()
            .messages()
            .get(userId="me", id=reply_to_message_id, format="metadata", metadataHeaders=["Message-ID"])
            .execute()
        )
        message["threadId"] = orig["threadId"]
        mid = next((x["value"] for x in orig["payload"]["headers"] if x["name"].lower() == "message-id"), "")
        if mid:
            msg["In-Reply-To"] = mid
            msg["References"] = mid
    message["raw"] = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().drafts().create(userId="me", body={"message": message}).execute()
    return f"Draft saved in Gmail for {to}. Nothing was sent."
