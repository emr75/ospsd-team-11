locals {
  env_vars = {
    GOOGLE_CALENDAR_CLIENT_ID                   = var.google_calendar_client_id
    GOOGLE_CALENDAR_CLIENT_SECRET               = var.google_calendar_client_secret
    GOOGLE_CALENDAR_TOKEN_URI                   = var.google_calendar_token_uri
    GOOGLE_CALENDAR_REFRESH_TOKEN               = var.google_calendar_refresh_token
    GOOGLE_CALENDAR_REDIRECT_URI                = var.google_calendar_redirect_uri
    GOOGLE_CALENDAR_SCOPES                      = var.google_calendar_scopes
    GOOGLE_CALENDAR_OAUTH_AUTH_URL              = var.google_calendar_oauth_auth_url
    GOOGLE_CALENDAR_OAUTH_TOKEN_URL             = var.google_calendar_oauth_token_url
    GOOGLE_CALENDAR_OAUTH_ALLOWED_TOKEN_HOSTS   = var.google_calendar_oauth_allowed_token_hosts
    GOOGLE_CALENDAR_OAUTH_PROMPT                = var.google_calendar_oauth_prompt
    GOOGLE_CALENDAR_OAUTH_STATE_TTL_SECONDS     = var.google_calendar_oauth_state_ttl_seconds
    GOOGLE_CALENDAR_OAUTH_TOKEN_TIMEOUT_SECONDS = var.google_calendar_oauth_token_timeout_seconds
    GOOGLE_CALENDAR_SESSION_COOKIE_NAME         = var.google_calendar_session_cookie_name
    GOOGLE_CALENDAR_SESSION_IDENTIFIER          = var.google_calendar_session_identifier
    GOOGLE_CALENDAR_SESSION_SECRET              = var.google_calendar_session_secret
    GOOGLE_CALENDAR_SESSION_COOKIE_SECURE       = var.google_calendar_session_cookie_secure
    CALENDAR_COOKIE_ID                          = var.calendar_cookie_id
    CALENDAR_COOKIE_VALUE                       = var.calendar_cookie_value
    CALENDAR_SERVICE_BASE_URL                   = var.calendar_service_base_url
    DEFAULT_CALENDAR_ID                         = var.default_calendar_id

    OPENAI_API_KEY = var.openai_api_key

    TRELLO_API_KEY   = var.trello_api_key
    TRELLO_API_TOKEN = var.trello_api_token
    TRELLO_BOARD_ID  = var.trello_board_id

    OTEL_SERVICE_NAME           = var.otel_service_name
    OTEL_EXPORTER_OTLP_ENDPOINT = var.otel_exporter_otlp_endpoint
    OTEL_EXPORTER_OTLP_PROTOCOL = var.otel_exporter_otlp_protocol
    OTEL_RESOURCE_ATTRIBUTES    = var.otel_resource_attributes
    OTEL_EXPORTER_OTLP_HEADERS  = var.otel_exporter_otlp_headers
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
