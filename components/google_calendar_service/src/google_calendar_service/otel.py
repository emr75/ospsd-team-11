"""OpenTelemetry provider setup for the Google Calendar service."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler  # type: ignore[import-not-found]
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor  # type: ignore[import-not-found]
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response

log: Any = logging.getLogger(__name__)
MIN_QUOTED_VALUE_LENGTH = 2

request_counter: Counter | None = None
request_duration: Histogram | None = None


def _status_group(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _resolve_route(request: Request) -> str:
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return request.url.path


def _configure_metric_instruments() -> None:
    global request_counter, request_duration  # noqa: PLW0603 - instrumentation is configured once at app startup.

    meter = metrics.get_meter("google-calendar-service")
    request_counter = meter.create_counter(
        name="http.requests.total",
        description="Total HTTP requests by method, route, and status group",
    )
    request_duration = meter.create_histogram(
        name="http.request.duration_seconds",
        description="HTTP request latency in seconds",
        unit="s",
    )


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request count and latency as OTEL metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Record request telemetry before returning the response."""
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        route = _resolve_route(request)
        status = _status_group(response.status_code)
        attrs = {"method": request.method, "route": route, "status": status}

        if request_counter is not None:
            request_counter.add(1, attrs)
        if request_duration is not None:
            request_duration.record(elapsed, attrs)

        return response


def configure_opentelemetry() -> None:
    """Configure OpenTelemetry providers and exporters.

    Reads standard OTEL env vars (OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_HEADERS, OTEL_SERVICE_NAME, etc.).
    If the endpoint is not set, telemetry is disabled.
    """
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        log.warning("Telemetry disabled: OTEL_EXPORTER_OTLP_ENDPOINT not set")
        return

    resource = Resource.create()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(meter_provider)
    _configure_metric_instruments()

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))

    tracer = trace.get_tracer("google-calendar-service.startup")
    with tracer.start_as_current_span("service.startup"):
        log.info("OpenTelemetry configured for google-calendar-service")
