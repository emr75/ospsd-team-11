# ---------------------------------------------------------------------------
# Non-secret env vars are safe to live in Terraform state.
# Secret env vars (API keys, OAuth secrets, tokens) are set directly in
# Render so they never appear in the state file.
#
# Secrets to directly configure in Render:
#   GOOGLE_CALENDAR_CLIENT_ID
#   GOOGLE_CALENDAR_CLIENT_SECRET
#   GOOGLE_CALENDAR_REFRESH_TOKEN
#   GOOGLE_CALENDAR_SESSION_SECRET
#   CALENDAR_COOKIE_VALUE
#   OPENAI_API_KEY
#   ISSUE_TRACKER_SERVICE_URL
#   ISSUE_TRACKER_SESSION_ID
#   OTEL_EXPORTER_OTLP_HEADERS
# ---------------------------------------------------------------------------
locals {
  # Environment Variables (non-secret configuration)
  env_vars = {
    # Google Calendar OAuth
    GOOGLE_CALENDAR_TOKEN_URI                   = var.google_calendar_token_uri
    GOOGLE_CALENDAR_REDIRECT_URI                = var.google_calendar_redirect_uri
    GOOGLE_CALENDAR_SCOPES                      = var.google_calendar_scopes
    GOOGLE_CALENDAR_OAUTH_AUTH_URL              = var.google_calendar_oauth_auth_url
    GOOGLE_CALENDAR_OAUTH_TOKEN_URL             = var.google_calendar_oauth_token_url
    GOOGLE_CALENDAR_OAUTH_ALLOWED_TOKEN_HOSTS   = var.google_calendar_oauth_allowed_token_hosts
    GOOGLE_CALENDAR_OAUTH_PROMPT                = var.google_calendar_oauth_prompt
    GOOGLE_CALENDAR_OAUTH_STATE_TTL_SECONDS     = var.google_calendar_oauth_state_ttl_seconds
    GOOGLE_CALENDAR_OAUTH_TOKEN_TIMEOUT_SECONDS = var.google_calendar_oauth_token_timeout_seconds

    # Session
    GOOGLE_CALENDAR_SESSION_COOKIE_NAME   = var.google_calendar_session_cookie_name
    GOOGLE_CALENDAR_SESSION_IDENTIFIER    = var.google_calendar_session_identifier
    GOOGLE_CALENDAR_SESSION_COOKIE_SECURE = var.google_calendar_session_cookie_secure

    # Service adapter
    CALENDAR_COOKIE_ID        = var.calendar_cookie_id
    CALENDAR_SERVICE_BASE_URL = var.calendar_service_base_url
    DEFAULT_CALENDAR_ID       = var.default_calendar_id

    # OpenTelemetry
    OTEL_SERVICE_NAME           = var.otel_service_name
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_exporter_otlp_endpoint
    OTEL_EXPORTER_OTLP_PROTOCOL = var.otel_exporter_otlp_protocol
    OTEL_RESOURCE_ATTRIBUTES    = var.otel_resource_attributes
  }
}

resource "render_web_service" "app" {
  name   = var.service_name
  plan   = var.plan
  region = var.region

  health_check_path = var.health_check_path
  root_directory    = var.root_dir != "" ? var.root_dir : null
  start_command     = var.docker_command != "" ? var.docker_command : null

  runtime_source = {
    docker = {
      repo_url    = var.repo_url
      branch      = var.branch
      auto_deploy = true
    }
  }

  env_vars = {
    for key, value in local.env_vars : key => {
      value = value
    }
  }
}
