"""Conservative accounting for the owner-authorized cumulative Meta limit."""

from sqlalchemy import func, select

from backend.app.models.database import AuditEvent

AUTHORIZED_REQUESTS = 1000
REQUEST_START_EVENTS = ("MUSE_ANALYSIS_STARTED", "SAM_SEGMENTATION_STARTED", "AGENT_MODEL_STARTED")


def meta_request_budget(db) -> dict:
    used = db.scalar(select(func.count()).select_from(AuditEvent).where(
        AuditEvent.event_type.in_(REQUEST_START_EVENTS))) or 0
    return {"authorized_requests": AUTHORIZED_REQUESTS, "recorded_attempts": used,
            "remaining_requests": max(0, AUTHORIZED_REQUESTS - used),
            "inspection_required_requests": 5, "investigation_required_requests": 7}
