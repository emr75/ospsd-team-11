"""AI routes for handling assistant interactions."""

from __future__ import annotations

import logging
from typing import cast

from ai_client_api import get_client as get_ai_client
from calendar_client_api import get_client as get_calendar_client
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from google_calendar_service.agent import CalendarClientProtocol, run_ai_turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class AiRequest(BaseModel):
    """Incoming AI request payload."""

    prompt: str
    context: dict[str, object] | None = None


class AiResponseModel(BaseModel):
    """Serialized AI response returned by the route."""

    message: str


@router.post("/")
def handle_ai(request: AiRequest) -> AiResponseModel:
    """Handle an AI prompt through the AI orchestration flow."""
    try:
        ai_client = get_ai_client()
        calendar_client = cast("CalendarClientProtocol", get_calendar_client())

        answer = run_ai_turn(
            prompt=request.prompt,
            context=request.context,
            ai_client=ai_client,
            calendar_client=calendar_client,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        logger.warning("AI route runtime failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected AI route failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected AI route failure.",
        ) from exc

    return AiResponseModel(message=answer)
