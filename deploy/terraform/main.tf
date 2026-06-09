terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Retrieve project metadata to dynamically resolve the project number
data "google_project" "project" {
  project_id = var.project_id
}

locals {
  # List of APIs needed for Agent Engine, container builds, and Drive export
  services = [
    "aiplatform.googleapis.com",      # Vertex AI
    "drive.googleapis.com",           # Google Drive API
    "iam.googleapis.com",             # Identity and Access Management
    "cloudbuild.googleapis.com",      # Cloud Build (for packaging agent code)
    "artifactregistry.googleapis.com" # Artifact Registry (for storing agent containers)
  ]

  # Default session bucket name if not overridden
  resolved_bucket_name = var.bucket_name != "" ? var.bucket_name : "slide-gen-sessions-${var.project_id}"

  # Runtime SA: Google-managed identity that executes Vertex AI Reasoning Engine code
  runtime_sa = "service-${data.google_project.project.number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

  # Build SA: Default Compute Engine service account used during 'adk deploy' for container builds
  build_sa = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# 1. Enable Required GCP APIs
resource "google_project_service" "services" {
  for_each           = toset(local.services)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false # Avoid disabling core APIs if the TF workspace is destroyed
}

# 2. Create the GCS Session Bucket
resource "google_storage_bucket" "sessions" {
  name                        = local.resolved_bucket_name
  location                    = var.region
  project                     = var.project_id
  force_destroy               = false # Prevent accidental deletion of user presentations
  uniform_bucket_level_access = true

  # Ensure APIs are enabled first
  depends_on = [google_project_service.services]
}

# 3. Create the user-managed Service Account for Google Drive Domain-Wide Delegation
resource "google_service_account" "drive_exporter" {
  account_id   = "slide-gen-drive"
  display_name = "Slide Gen Drive Exporter"
  description  = "Service account for slide-gen-agent Google Drive export (Domain-Wide Delegation)"
  project      = var.project_id

  # Ensure APIs are enabled first
  depends_on = [google_project_service.services]
}

# 4. Project-Level IAM: Grant Vertex AI permissions to the Runtime SA
resource "google_project_iam_member" "runtime_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${local.runtime_sa}"

  depends_on = [google_project_service.services]
}

# 5. Project-Level IAM: Grant GCS permissions to the Runtime SA
resource "google_project_iam_member" "runtime_storage_user" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${local.runtime_sa}"

  depends_on = [google_project_service.services]
}

# 6. Project-Level IAM: Grant Build permissions to the Build SA (Compute Engine SA)
resource "google_project_iam_member" "build_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${local.build_sa}"

  depends_on = [google_project_service.services]
}

resource "google_project_iam_member" "build_artifactregistry" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${local.build_sa}"

  depends_on = [google_project_service.services]
}

# 7. Resource-Level IAM: Allow the Runtime SA to impersonate the Drive SA (sign JWTs)
# Note: This is applied directly to the Drive SA resource, NOT the project level.
resource "google_service_account_iam_member" "runtime_impersonate_drive" {
  service_account_id = google_service_account.drive_exporter.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${local.runtime_sa}"
}
