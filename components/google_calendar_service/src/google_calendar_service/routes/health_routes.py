"""Health check routes for the Google Calendar Service."""

from fastapi import APIRouter

from google_calendar_service.models import StatusResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/health")
def health() -> StatusResponse:
    """Return service health status."""
    return StatusResponse(status="ok")
