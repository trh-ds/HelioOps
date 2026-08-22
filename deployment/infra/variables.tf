variable "region" {
  description = "AWS region. Groq is us-east hosted, so us-east-1 shaves an RTT off every LLM call."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Name prefix for every resource."
  type        = string
  default     = "helioops"
}

variable "domain" {
  description = "Hostname the API answers on. Must resolve to the Elastic IP before Caddy can issue a certificate."
  type        = string
  default     = "api.heliops.dpdns.org"
}

variable "cors_origins" {
  description = <<-EOT
    JSON array for HELIOOPS_CORS_ORIGINS. pydantic-settings parses list[str] as
    JSON. It REPLACES the defaults in backend/config.py, so list every origin
    including the Vercel preview one or previews break with WS close 4003.
  EOT
  type        = string
  default     = "[\"https://heliops.dpdns.org\"]"
}

variable "instance_type" {
  description = <<-EOT
    t3.small (2 GB) is the floor: torch plus the bge-small embedder sit around
    963 MB RSS (see backend/__init__.py), and user_data adds 2 GB of swap to
    cover the ingest//api/detect peaks. Move to t3.medium if the box starts
    swapping under load — check `free -m` over a run before paying for it.
  EOT
  type        = string
  default     = "t3.small"
}

variable "root_volume_gb" {
  description = "Root EBS size. The image is ~3 GB and Docker keeps the previous one until pruned, so 30 GB leaves room for a rollback."
  type        = number
  default     = 30
}

variable "github_repo" {
  description = "owner/repo allowed to assume the deploy role via OIDC. Empty disables the CI role entirely."
  type        = string
  default     = ""
}
