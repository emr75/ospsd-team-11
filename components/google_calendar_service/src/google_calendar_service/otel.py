"""OpenTelemetry provider setup for the Google Calendar service.

Metrics follow the `OpenTelemetry HTTP Semantic Conventions
<https://opentelemetry.io/docs/specs/semconv/http/http-metrics/>`_.
``FastAPIInstrumentor`` automatically records the stable
``http.server.request.duration`` histogram with attributes
``http.request.method``, ``http.response.status_code``, ``http.route``,
and ``url.scheme``.  No custom middleware is needed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

log: Any = logging.getLogger(__name__)


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

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    logging.getLogger().addHandler(LoggingHandler(logger_provider=logger_provider))

    tracer = trace.get_tracer("google-calendar-service.startup")
    with tracer.start_as_current_span("service.startup"):
        log.info("OpenTelemetry configured for google-calendar-service")
