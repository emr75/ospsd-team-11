"""AI routes for handling assistant interactions."""

import logging
from typing import TYPE_CHECKING, Annotated, cast

from ai_client_api import AiClient
from api.client import Client as IssueClient  # type: ignore[import-untyped]
from calendar_client_api import CalendarClient
from fastapi import APIRouter, Depends, HTTPException, status

from google_calendar_service.deps import get_ai_client, get_calendar_client, get_issue_client
from google_calendar_service.integrations.agent import run_ai_turn
from google_calendar_service.models import AiRequest, AiResponseModel

if TYPE_CHECKING:
    from google_calendar_service.integrations.protocol import CalendarClientProtocol, IssueClientProtocol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/")
def handle_ai(
    request: AiRequest,
    ai_client: Annotated[AiClient, Depends(get_ai_client)],
    calendar_client: Annotated[CalendarClient, Depends(get_calendar_client)],
    issue_client: Annotated[IssueClient, Depends(get_issue_client)],
) -> AiResponseModel:
    """Handle an AI prompt through the AI orchestration flow."""
    try:
        cast_calendar_client = cast("CalendarClientProtocol", calendar_client)
        cast_issue_client = cast("IssueClientProtocol", issue_client)

        answer = run_ai_turn(
            prompt=request.prompt,
            context=request.context,
            ai_client=ai_client,
            calendar_client=cast_calendar_client,
            issue_client=cast_issue_client,
        )
    except ValueError as exc:
        logger.info("AI route validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid AI request. Check the prompt and context fields.",
        ) from exc
    except RuntimeError as exc:
        logger.warning("AI route runtime failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please try again later.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected AI route failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing the AI request.",
        ) from exc

    return AiResponseModel(message=answer)
