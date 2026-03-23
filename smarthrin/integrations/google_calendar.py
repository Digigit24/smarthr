"""
Google Calendar Integration — create, update, cancel events with Google Meet links.

Uses a Google Cloud service account with domain-wide delegation.
Configure via environment variables:
    GOOGLE_CALENDAR_CREDENTIALS_JSON — Service account key JSON (raw JSON string)
    GOOGLE_CALENDAR_DELEGATE_EMAIL   — Admin email for domain-wide delegation

If credentials are not configured, all functions return gracefully
so interview CRUD is never blocked by missing calendar config.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class CalendarNotConfigured(Exception):
    """Raised when Google Calendar credentials are not set up."""
    pass


class CalendarAPIError(Exception):
    """Raised when the Google Calendar API returns an error."""
    pass


def _get_calendar_service():
    """
    Build and return an authenticated Google Calendar API service.

    Raises CalendarNotConfigured if credentials are missing.
    """
    credentials_json = getattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_JSON", "")
    delegate_email = getattr(settings, "GOOGLE_CALENDAR_DELEGATE_EMAIL", "")

    if not credentials_json or not delegate_email:
        raise CalendarNotConfigured(
            "Google Calendar is not configured. "
            "Set GOOGLE_CALENDAR_CREDENTIALS_JSON and GOOGLE_CALENDAR_DELEGATE_EMAIL."
        )

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise CalendarNotConfigured(
            "Google Calendar libraries not installed. "
            "Run: pip install google-auth google-api-python-client"
        )

    try:
        if isinstance(credentials_json, str):
            creds_info = json.loads(credentials_json)
        else:
            creds_info = credentials_json

        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        # Delegate to the admin email so events appear on real calendars
        delegated = credentials.with_subject(delegate_email)

        service = build("calendar", "v3", credentials=delegated, cache_discovery=False)
        return service
    except Exception as exc:
        raise CalendarAPIError(f"Failed to initialize Google Calendar service: {exc}") from exc


def is_configured() -> bool:
    """Check whether Google Calendar credentials are present in settings."""
    credentials_json = getattr(settings, "GOOGLE_CALENDAR_CREDENTIALS_JSON", "")
    delegate_email = getattr(settings, "GOOGLE_CALENDAR_DELEGATE_EMAIL", "")
    return bool(credentials_json and delegate_email)


def create_event(
    *,
    interviewer_email: str,
    attendees: list[str],
    start_time: datetime,
    duration_minutes: int = 60,
    title: str = "Interview",
    description: str = "",
) -> dict:
    """
    Create a Google Calendar event with an auto-generated Google Meet link.

    Returns:
        {"event_id": str, "meeting_link": str, "html_link": str}

    Raises:
        CalendarNotConfigured — credentials missing (caller should handle gracefully)
        CalendarAPIError — API call failed
    """
    service = _get_calendar_service()

    end_time = start_time + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": title,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC",
        },
        "attendees": [{"email": email} for email in attendees if email],
        "conferenceData": {
            "createRequest": {
                "requestId": f"smarthr-{start_time.strftime('%Y%m%d%H%M%S')}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    # Add interviewer as organizer attendee
    if interviewer_email:
        existing_emails = {a["email"] for a in event_body["attendees"]}
        if interviewer_email not in existing_emails:
            event_body["attendees"].append({"email": interviewer_email})

    try:
        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            )
            .execute()
        )
    except Exception as exc:
        raise CalendarAPIError(f"Failed to create calendar event: {exc}") from exc

    meeting_link = ""
    conference_data = event.get("conferenceData", {})
    for entry_point in conference_data.get("entryPoints", []):
        if entry_point.get("entryPointType") == "video":
            meeting_link = entry_point.get("uri", "")
            break

    return {
        "event_id": event["id"],
        "meeting_link": meeting_link,
        "html_link": event.get("htmlLink", ""),
    }


def update_event(
    *,
    event_id: str,
    start_time: Optional[datetime] = None,
    duration_minutes: Optional[int] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[list[str]] = None,
) -> dict:
    """
    Update an existing Google Calendar event.

    Only provided fields are updated. Returns the updated event data.

    Raises:
        CalendarNotConfigured, CalendarAPIError
    """
    service = _get_calendar_service()

    try:
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:
        raise CalendarAPIError(f"Failed to fetch event {event_id}: {exc}") from exc

    if title is not None:
        event["summary"] = title
    if description is not None:
        event["description"] = description
    if start_time is not None:
        event["start"] = {"dateTime": start_time.isoformat(), "timeZone": "UTC"}
        end_time = start_time + timedelta(minutes=duration_minutes or 60)
        event["end"] = {"dateTime": end_time.isoformat(), "timeZone": "UTC"}
    elif duration_minutes is not None and "start" in event:
        start_dt = datetime.fromisoformat(event["start"]["dateTime"])
        end_time = start_dt + timedelta(minutes=duration_minutes)
        event["end"] = {"dateTime": end_time.isoformat(), "timeZone": "UTC"}
    if attendees is not None:
        event["attendees"] = [{"email": email} for email in attendees if email]

    try:
        updated = (
            service.events()
            .update(
                calendarId="primary",
                eventId=event_id,
                body=event,
                sendUpdates="all",
            )
            .execute()
        )
    except Exception as exc:
        raise CalendarAPIError(f"Failed to update event {event_id}: {exc}") from exc

    return {
        "event_id": updated["id"],
        "html_link": updated.get("htmlLink", ""),
    }


def cancel_event(event_id: str) -> None:
    """
    Cancel (delete) a Google Calendar event and notify attendees.

    Raises:
        CalendarNotConfigured, CalendarAPIError
    """
    service = _get_calendar_service()

    try:
        service.events().delete(
            calendarId="primary",
            eventId=event_id,
            sendUpdates="all",
        ).execute()
    except Exception as exc:
        raise CalendarAPIError(f"Failed to cancel event {event_id}: {exc}") from exc
