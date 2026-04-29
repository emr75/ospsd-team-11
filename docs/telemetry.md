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

## Telemetry Emitter

The FastAPI service exposes Prometheus metrics at:

```text
GET /metrics
```

The app uses `prometheus-fastapi-instrumentator` in `google_calendar_service.main`, which emits:

- `http_request_duration_seconds` for request latency.
- `http_requests_total` labeled by route, method, and status group for success and failure rates.

## Local Monitoring Stack

The `monitoring/` directory contains a local Prometheus and Grafana stack for collecting and visualizing the service metrics.

Start it from the repository root:

```bash
docker compose -f monitoring/docker-compose.yml up --build
```

Then open:

- Service: `http://localhost:8000`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Grafana is provisioned with a Prometheus data source and the `Calendar Service Observability` dashboard.

## Dashboard Queries

Request latency:

```promql
sum(rate(http_request_duration_seconds_sum[5m])) by (handler)
/
sum(rate(http_request_duration_seconds_count[5m])) by (handler)
```

Success rate:

```promql
100 * sum(rate(http_requests_total{status=~"2xx|3xx"}[5m]))
/
sum(rate(http_requests_total[5m]))
```

Failure rate:

```promql
100 * sum(rate(http_requests_total{status=~"4xx|5xx"}[5m]))
/
sum(rate(http_requests_total[5m]))
```

## Deployment Note

For the final demo, the deployed service must remain reachable at `/metrics` so an observability platform can scrape it. For a class demo, the local Prometheus/Grafana stack can be pointed at the deployed service by changing `monitoring/prometheus/prometheus.yml` from `app:8000` to the deployed host.
