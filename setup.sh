#!/bin/bash
set -e

PROJECT_ID="${1:?Usage: bash setup.sh <PROJECT_ID> [REGION] [--cleanup]}"
REGION="${2:-us-central1}"

if [ "$1" = "--cleanup" ] || [ "$2" = "--cleanup" ] || [ "$3" = "--cleanup" ]; then
    echo "Cleaning up setup resources for project: $PROJECT_ID..."
    BUCKET_NAME="slide-gen-sessions-${PROJECT_ID}"
    if gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
        echo "Removing Cloud Storage bucket gs://${BUCKET_NAME}..."
        gcloud storage rm -r "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" || true
    fi
    echo "Cleanup complete."
    exit 0
fi

echo "Setting up GCP resources for slide-gen-agent in project: $PROJECT_ID (region: $REGION)..."
echo "⚠️ Note: Vertex AI and Cloud Storage are paid GCP services."

gcloud config set project "$PROJECT_ID" --quiet

echo "Enabling required GCP APIs..."
gcloud services enable \
    aiplatform.googleapis.com \
    storage.googleapis.com \
    drive.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    --project="$PROJECT_ID" --quiet

BUCKET_NAME="slide-gen-sessions-${PROJECT_ID}"
echo "Checking Cloud Storage session bucket: gs://${BUCKET_NAME}..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "Creating Cloud Storage bucket gs://${BUCKET_NAME}..."
    gcloud storage buckets create "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" --location="${REGION}" --quiet
else
    echo "Bucket gs://${BUCKET_NAME} already exists."
fi

echo "GCP Setup Complete!"
