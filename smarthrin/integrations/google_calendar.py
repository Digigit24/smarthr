"""
Google Calendar Integration — Phase 2 Stub.

This module will provide calendar event creation and management
for interview scheduling. In Phase 2, this will:

1. Authenticate with Google Calendar API using OAuth2 service account
   or user-delegated credentials stored per-tenant.
2. create_event(interviewer_email, attendees, start_time, duration_minutes, title, description)
   → Creates a Google Calendar event and returns the event_id + Google Meet link.
3. update_event(event_id, **kwargs)
   → Updates an existing calendar event (reschedule, add attendees, etc.)
4. cancel_event(event_id)
   → Cancels the event and sends cancellation notices to attendees.
5. get_availability(email, start, end)
   → Returns busy/free slots for a user within a time window.

Configuration (per-tenant, stored in a future TenantIntegration model):
    GOOGLE_CALENDAR_CREDENTIALS_JSON — Service account JSON
    GOOGLE_CALENDAR_DELEGATE_EMAIL — Admin email for domain-wide delegation

Phase 2 implementation will use:
    google-auth, google-auth-oauthlib, google-api-python-client
"""


def create_event(
    interviewer_email: str,
    attendees: list[str],
    start_time: str,
    duration_minutes: int = 60,
    title: str = "Interview",
    description: str = "",
) -> dict:
    """STUB: Create a Google Calendar event. Phase 2 implementation pending."""
    raise NotImplementedError(
        "Google Calendar integration is not yet implemented. "
        "This will be implemented in Phase 2."
    )


def cancel_event(event_id: str) -> None:
    """STUB: Cancel a Google Calendar event. Phase 2 implementation pending."""
    raise NotImplementedError("Google Calendar integration is not yet implemented.")
