output "project_id" {
  value       = var.project_id
  description = "The GCP Project ID."
}

output "region" {
  value       = var.region
  description = "The GCP Region."
}

output "gcs_bucket_name" {
  value       = google_storage_bucket.sessions.name
  description = "The name of the created GCS bucket for sessions."
}

output "drive_sa_email" {
  value       = google_service_account.drive_exporter.email
  description = "The email of the created Google Drive exporter Service Account."
}

output "drive_sa_client_id" {
  value       = google_service_account.drive_exporter.unique_id
  description = "The OAuth2 Client ID of the Drive exporter Service Account (use this for Domain-Wide Delegation)."
}
