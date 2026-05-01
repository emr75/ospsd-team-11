"""FastAPI service endpoints for the Google Calendar service component."""

from __future__ import annotations

import openai_ai_client_impl  # noqa: F401
from dotenv import load_dotenv
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.responses import RedirectResponse

from google_calendar_service.otel import MetricsMiddleware, configure_opentelemetry
from google_calendar_service.routes.ai_routes import router as ai_router
from google_calendar_service.routes.auth_routes import router as auth_router
from google_calendar_service.routes.event_routes import router as event_router
from google_calendar_service.routes.health_routes import router as health_router

load_dotenv()

configure_opentelemetry()

app = FastAPI(
    title="Google Calendar Service",
    version="0.1.0",
)

FastAPIInstrumentor.instrument_app(app)
app.add_middleware(MetricsMiddleware)


@app.get("/")
def root() -> RedirectResponse:
    """Redirect root endpoint to /docs."""
    return RedirectResponse(url="/docs")


app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(event_router)
