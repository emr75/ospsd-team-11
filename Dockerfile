# Builder stage
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.21 /uv /uvx /usr/local/bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Copy workspace metadata first for better layer caching
COPY pyproject.toml uv.lock ./
COPY components/calendar_client_api/pyproject.toml components/calendar_client_api/pyproject.toml
COPY components/google_calendar_client_impl/pyproject.toml components/google_calendar_client_impl/pyproject.toml
COPY components/google_calendar_service/pyproject.toml components/google_calendar_service/pyproject.toml

# Pre-sync third-party runtime dependencies
RUN uv sync --frozen --no-dev --no-editable --no-install-workspace --package google-calendar-service

# Copy only the packages needed by google-calendar-service
COPY components/calendar_client_api components/calendar_client_api
COPY components/google_calendar_client_impl components/google_calendar_client_impl
COPY components/google_calendar_service components/google_calendar_service

# Install workspace packages into the existing environment
RUN uv sync --frozen --no-dev --no-editable --package google-calendar-service

# Runtime stage
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Copy the fully resolved virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Run as non-root
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "google_calendar_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
