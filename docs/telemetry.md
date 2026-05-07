# IaC and Telemetry

## Infrastructure as Code

The service infrastructure is managed with Terraform in `infra/`.

Terraform provisions the Render web service, configures Docker deployment from the repository, sets the service health check, and manages application environment variables. The deployed service exposes the FastAPI application from the repository `Dockerfile`.

Typical workflow:

```bash
cd infra
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Use `infra/terraform.tfvars.example` as the template for the real variable file. Do not commit real secrets.

## Telemetry

The FastAPI service is instrumented with the [OpenTelemetry](https://opentelemetry.io/) SDK and exports **traces**, **metrics**, and **logs** directly to [Grafana Cloud](https://grafana.com/products/cloud/) via OTLP.

### What is collected

All metric and attribute names follow the [OpenTelemetry HTTP Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/http/http-metrics/).

- **Traces** — one span per HTTP request, including route, method, status code, and latency. Provided automatically by `opentelemetry-instrumentation-fastapi`.
- **Metrics** — `http.server.request.duration` histogram (unit: seconds) with attributes `http.request.method`, `http.response.status_code`, `http.route`, and `url.scheme`. Provided automatically by `FastAPIInstrumentor`. Total request counts are derived from the histogram's implicit count.
- **Logs** — Python `logging` output bridged into OTLP and correlated with the active trace.

### Dashboard Queries (Grafana Cloud → Explore → Prometheus)

Request latency by route:

```promql
rate(http_server_request_duration_seconds_sum[5m])
/ rate(http_server_request_duration_seconds_count[5m])
```

Success rate:

```promql
100 * sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"2.."}[5m]))
/ sum(rate(http_server_request_duration_seconds_count[5m]))
```

Failure rate:

```promql
100 * sum(rate(http_server_request_duration_seconds_count{http_response_status_code=~"[45].."}[5m]))
/ sum(rate(http_server_request_duration_seconds_count[5m]))
```

### Architecture

```
FastAPI app  →  Grafana Cloud OTLP endpoint  (traces  → Tempo)
(any environment)                             (metrics → Prometheus)
                                              (logs    → Loki)
```

The app exports directly to Grafana Cloud — no collector sidecar required. If `OTEL_EXPORTER_OTLP_ENDPOINT` is absent the app starts normally with telemetry silently disabled.

## Setup

Add the following standard OTEL env vars to your `.env` (see `.env.example`):

```
OTEL_SERVICE_NAME=google-calendar-service
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-<region>.grafana.net/otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_RESOURCE_ATTRIBUTES=service.namespace=ospsd-team-11
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<your-base64-token>
```

Find these values in Grafana Cloud → My Account → your stack → OpenTelemetry → "Programmatic setup".

## Local Development

```bash
docker compose -f monitoring/docker-compose.yml up --build
```

The app reads `.env` from the repo root, so telemetry works locally as long as the OTEL vars are set. Open the service at `http://localhost:8000`.

Telemetry is visible in Grafana Cloud under **Explore → Tempo** (traces), **Explore → Prometheus** (metrics), and **Explore → Loki** (logs).
