variable "project_id" {
  type        = string
  description = "The GCP Project ID where the agent will be deployed."
}

variable "region" {
  type        = string
  description = "The GCP Region where the Vertex AI Reasoning Engine and GCS bucket will reside."
  default     = "us-central1"
}

variable "bucket_name" {
  type        = string
  description = "The name of the GCS bucket for storing agent session artifacts. If omitted, defaults to slide-gen-sessions-<project_id>."
  default     = ""
}
