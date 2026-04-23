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
  type      = string
  sensitive = true
}

variable "google_calendar_client_secret" {
  type      = string
  sensitive = true
}

variable "google_calendar_token_uri" {
  type    = string
  default = "https://oauth2.googleapis.com/token"
}

variable "google_calendar_refresh_token" {
  type      = string
  sensitive = true
}

variable "google_calendar_redirect_uri" {
  type = string
}

variable "google_calendar_scopes" {
  type    = string
  default = "https://www.googleapis.com/auth/calendar"
}

variable "google_calendar_oauth_auth_url" {
  type    = string
  default = "https://accounts.google.com/o/oauth2/v2/auth"
}

variable "google_calendar_oauth_token_url" {
  type    = string
  default = "https://oauth2.googleapis.com/token"
}

variable "google_calendar_oauth_allowed_token_hosts" {
  type    = string
  default = "oauth2.googleapis.com"
}

variable "google_calendar_oauth_prompt" {
  type    = string
  default = "consent"
}

variable "google_calendar_oauth_state_ttl_seconds" {
  type    = string
  default = "600"
}

variable "google_calendar_oauth_token_timeout_seconds" {
  type    = string
  default = "10"
}

variable "google_calendar_session_cookie_name" {
  type    = string
  default = "google_calendar_session_id"
}

variable "google_calendar_session_identifier" {
  type    = string
  default = "google_calendar_service_verifier"
}

variable "google_calendar_session_secret" {
  type      = string
  sensitive = true
}

variable "google_calendar_session_cookie_secure" {
  type    = string
  default = "true"
}

variable "calendar_cookie_id" {
  type    = string
  default = "google_calendar_session_id"
}

variable "calendar_cookie_value" {
  type      = string
  sensitive = true
}

variable "calendar_service_base_url" {
  type = string
}

variable "default_calendar_id" {
  type    = string
  default = "primary"
}
