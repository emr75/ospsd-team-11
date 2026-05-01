variable "render_api_key" {
  description = "Render API key"
  type        = string
  sensitive   = true
}

variable "render_owner_id" {
  description = "Render owner ID (user or workspace owner ID)"
  type        = string
}

variable "service_name" {
  description = "Render web service name"
  type        = string
  default     = "google-calendar-service"
}

variable "repo_url" {
  description = "Git repository URL"
  type        = string
}

variable "branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "root_dir" {
  description = "Root directory of the app in the repo"
  type        = string
  default     = ""
}

variable "runtime" {
  description = "Render runtime"
  type        = string
  default     = "docker"
}

variable "plan" {
  description = "Render service plan"
  type        = string
  default     = "free"
}

variable "region" {
  description = "Render region"
  type        = string
  default     = "oregon"
}

variable "docker_command" {
  description = "Optional start command override"
  type        = string
  default     = ""
}

variable "health_check_path" {
  description = "Health check path"
  type        = string
  default     = "/health"
}

# ===== App env vars =====

variable "google_calendar_client_id" {
  description = "Google OAuth client ID for the Calendar service"
  type        = string
  sensitive   = true
}

variable "google_calendar_client_secret" {
  description = "Google OAuth client secret paired with google_calendar_client_id"
  type        = string
  sensitive   = true
}

variable "google_calendar_token_uri" {
  description = "Google OAuth token endpoint used to exchange/refresh tokens"
  type        = string
  default     = "https://oauth2.googleapis.com/token"
}

variable "google_calendar_refresh_token" {
  description = "Long-lived Google OAuth refresh token used for offline access"
  type        = string
  sensitive   = true
}

variable "google_calendar_redirect_uri" {
  description = "OAuth redirect URI registered in Google Cloud (must match the deployed /auth/callback URL)"
  type        = string
}

variable "google_calendar_scopes" {
  description = "Space-separated Google API scopes requested during the OAuth flow"
  type        = string
  default     = "https://www.googleapis.com/auth/calendar"
}

variable "google_calendar_oauth_auth_url" {
  description = "Google OAuth 2.0 authorization endpoint"
  type        = string
  default     = "https://accounts.google.com/o/oauth2/v2/auth"
}

variable "google_calendar_oauth_token_url" {
  description = "Google OAuth 2.0 token endpoint used by the FastAPI service"
  type        = string
  default     = "https://oauth2.googleapis.com/token"
}

variable "google_calendar_oauth_allowed_token_hosts" {
  description = "Comma-separated allow-list of hosts the service will exchange OAuth tokens with"
  type        = string
  default     = "oauth2.googleapis.com"
}

variable "google_calendar_oauth_prompt" {
  description = "OAuth 'prompt' parameter (e.g. 'consent', 'select_account')"
  type        = string
  default     = "consent"
}

variable "google_calendar_oauth_state_ttl_seconds" {
  description = "Time-to-live (seconds) for OAuth state/PKCE values stored in the session"
  type        = string
  default     = "600"
}

variable "google_calendar_oauth_token_timeout_seconds" {
  description = "HTTP timeout (seconds) for outbound OAuth token-exchange requests"
  type        = string
  default     = "10"
}

variable "google_calendar_session_cookie_name" {
  description = "Cookie name used by the service's session middleware"
  type        = string
  default     = "google_calendar_session_id"
}

variable "google_calendar_session_identifier" {
  description = "Session backend identifier (used by fastapi-sessions to namespace session data)"
  type        = string
  default     = "google_calendar_service_verifier"
}

variable "google_calendar_session_secret" {
  description = "Secret used to sign/verify session cookies"
  type        = string
  sensitive   = true
}

variable "google_calendar_session_cookie_secure" {
  description = "If 'true', the session cookie is marked Secure (HTTPS-only). Should be 'true' in production."
  type        = string
  default     = "true"
}

variable "calendar_cookie_id" {
  description = "Cookie name read by the service adapter when calling the deployed service"
  type        = string
  default     = "google_calendar_session_id"
}

variable "calendar_cookie_value" {
  description = "Cookie value used by the service adapter for authenticated calls to the deployed service"
  type        = string
  sensitive   = true
}

variable "calendar_service_base_url" {
  description = "Public base URL of the deployed FastAPI service (used by adapter clients)"
  type        = string
}

variable "default_calendar_id" {
  description = "Default Google calendar ID the service operates on when none is specified"
  type        = string
  default     = "primary"
}

# ===== AI / OpenAI =====

variable "openai_api_key" {
  description = "API key for OpenAI (used by openai_ai_client_impl)"
  type        = string
  sensitive   = true
}

# ===== Trello (issue tracker integration) =====

variable "trello_api_key" {
  description = "Trello API key used by the issue-tracker integration"
  type        = string
  sensitive   = true
}

variable "trello_api_token" {
  description = "Trello API token used by the issue-tracker integration"
  type        = string
  sensitive   = true
}

variable "trello_board_id" {
  description = "Trello board ID used by the issue-tracker integration"
  type        = string
}

# ===== OpenTelemetry =====
# All OTEL_* variables are optional. The service silently disables telemetry
# when OTEL_EXPORTER_OTLP_ENDPOINT is empty.

variable "otel_service_name" {
  description = "OpenTelemetry service name attached to all signals"
  type        = string
  default     = "google-calendar-service"
}

variable "otel_exporter_otlp_endpoint" {
  description = "OTLP/HTTP collector base URL (e.g. Grafana Cloud OTLP gateway). Leave empty to disable telemetry."
  type        = string
  default     = ""
}

variable "otel_exporter_otlp_protocol" {
  description = "OTLP wire protocol"
  type        = string
  default     = "http/protobuf"
}

variable "otel_resource_attributes" {
  description = "Comma-separated OTel resource attributes (e.g. service.namespace=ospsd-team-11)"
  type        = string
  default     = "service.namespace=ospsd-team-11"
}

variable "otel_exporter_otlp_headers" {
  description = "OTLP exporter headers (e.g. Authorization=Basic <base64>). Sensitive when carrying auth tokens."
  type        = string
  default     = ""
  sensitive   = true
}
