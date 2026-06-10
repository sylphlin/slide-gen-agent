#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "================================================================="
echo "🚀 Slide Gen Agent: One-Click Deploy to Gemini Enterprise"
echo "================================================================="

# Prerequisite Checks
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: terraform is not installed or not in PATH."
    echo "Please install Terraform (https://developer.hashicorp.com/terraform/downloads) and try again."
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed or not in PATH."
    echo "Please install the Google Cloud SDK (https://cloud.google.com/sdk/docs/install) and try again."
    exit 1
fi

# Verify gcloud authentication
ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")
if [ -z "$ACTIVE_ACCOUNT" ]; then
    echo "❌ Error: No active Google Cloud account found."
    echo "Please run 'gcloud auth login' and 'gcloud auth application-default login' first."
    exit 1
fi

# Detect Default Project
DEFAULT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")

# Prompt for Project ID
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    if [ -n "$DEFAULT_PROJECT" ]; then
        read -p "Enter GCP Project ID [default: $DEFAULT_PROJECT]: " GOOGLE_CLOUD_PROJECT
        GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT:-$DEFAULT_PROJECT}
    else
        read -p "Enter GCP Project ID: " GOOGLE_CLOUD_PROJECT
    fi
fi

if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "❌ Error: GCP Project ID is required."
    exit 1
fi

# Prompt for Region
read -p "Enter GCP Region [default: us-central1]: " REGION
REGION=${REGION:-us-central1}

echo ""
echo "Configuration Summary:"
echo "----------------------"
echo "Project ID: $GOOGLE_CLOUD_PROJECT"
echo "Region:     $REGION"
echo ""
read -p "Do you want to proceed with this configuration? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Step 1: Provision Infrastructure with Terraform
echo ""
echo "================================================================="
echo "Step 1: Provisioning GCP Infrastructure with Terraform..."
echo "================================================================="
cd deploy/terraform
terraform init

# Smart Check: Detect if the service account already exists in GCP
DRIVE_SA_EMAIL="slide-gen-drive@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
echo "Checking if Service Account $DRIVE_SA_EMAIL already exists..."

if gcloud iam service-accounts describe "$DRIVE_SA_EMAIL" --project="$GOOGLE_CLOUD_PROJECT" &>/dev/null; then
    echo ""
    echo "⚠️  Notice: Service Account '$DRIVE_SA_EMAIL' already exists in your GCP project."
    echo "This usually happens if you previously configured a manual deployment."
    echo ""
    echo "How would you like to resolve this conflict?"
    echo "1) [Recommended] Automatically import (adopt) the existing Service Account into Terraform"
    echo "2) Automatically delete the existing Service Account from GCP and let Terraform recreate it"
    echo "3) Cancel deployment"
    echo ""
    read -p "Enter your choice (1/2/3): " SA_CHOICE
    
    case "$SA_CHOICE" in
        1)
            echo "Importing existing Service Account into Terraform state..."
            # Run terraform import. We use || true to prevent script crash if it's already imported
            terraform import \
              -var="project_id=$GOOGLE_CLOUD_PROJECT" \
              -var="region=$REGION" \
              google_service_account.drive_exporter \
              "projects/${GOOGLE_CLOUD_PROJECT}/serviceAccounts/${DRIVE_SA_EMAIL}" || echo "Note: Proceeding with existing state."
            ;;
        2)
            echo "Deleting existing Service Account from GCP..."
            gcloud iam service-accounts delete "$DRIVE_SA_EMAIL" --project="$GOOGLE_CLOUD_PROJECT" --quiet
            echo "✅ Service Account deleted successfully."
            ;;
        *)
            echo "Deployment cancelled."
            exit 0
            ;;
    esac
fi

# Smart Check 2: Detect if the GCS Bucket already exists in GCP
RESOLVED_BUCKET_NAME="slide-gen-sessions-${GOOGLE_CLOUD_PROJECT}"
echo "Checking if GCS Bucket gs://$RESOLVED_BUCKET_NAME already exists..."

if gcloud storage buckets describe "gs://$RESOLVED_BUCKET_NAME" --project="$GOOGLE_CLOUD_PROJECT" &>/dev/null; then
    echo ""
    echo "⚠️  Notice: GCS Bucket 'gs://$RESOLVED_BUCKET_NAME' already exists in your GCP project."
    echo "This usually happens if you previously performed a manual installation."
    echo ""
    echo "How would you like to resolve this conflict?"
    echo "1) [Recommended] Automatically import (adopt) the existing Bucket into Terraform"
    echo "   (This preserves all your existing slide sessions and generated files!)"
    echo "2) Automatically delete the existing Bucket from GCP and let Terraform recreate it"
    echo "   ⚠️  WARNING: Option 2 will permanently delete all files and history inside the bucket!"
    echo "3) Cancel deployment"
    echo ""
    read -p "Enter your choice (1/2/3): " BUCKET_CHOICE
    
    case "$BUCKET_CHOICE" in
        1)
            echo "Importing existing GCS Bucket into Terraform state..."
            terraform import \
              -var="project_id=$GOOGLE_CLOUD_PROJECT" \
              -var="region=$REGION" \
              google_storage_bucket.sessions \
              "$RESOLVED_BUCKET_NAME" || echo "Note: Proceeding with existing bucket state."
            ;;
        2)
            echo "Deleting existing GCS Bucket from GCP..."
            # Delete objects first to ensure non-empty bucket deletion succeeds
            gcloud storage rm -r "gs://$RESOLVED_BUCKET_NAME" --project="$GOOGLE_CLOUD_PROJECT" || true
            # Delete the bucket
            gcloud storage buckets delete "gs://$RESOLVED_BUCKET_NAME" --project="$GOOGLE_CLOUD_PROJECT" --quiet
            echo "✅ GCS Bucket deleted successfully."
            ;;
        *)
            echo "Deployment cancelled."
            exit 0
            ;;
    esac
fi

echo "Applying Terraform configuration..."

terraform apply \
  -var="project_id=$GOOGLE_CLOUD_PROJECT" \
  -var="region=$REGION" \
  -auto-approve


# Extract Terraform Outputs
BUCKET_NAME=$(terraform output -raw gcs_bucket_name)
DRIVE_SA_EMAIL=$(terraform output -raw drive_sa_email)
DRIVE_SA_CLIENT_ID=$(terraform output -raw drive_sa_client_id)
cd ../..

# Step 2: Generate .env Configuration File
echo ""
echo "================================================================="
echo "Step 2: Generating adk_agent/.env configuration..."
echo "================================================================="
cat > adk_agent/.env <<EOF
# Generated automatically by deploy.sh on $(date)
GOOGLE_CLOUD_PROJECT="$GOOGLE_CLOUD_PROJECT"
DRIVE_SA_EMAIL="$DRIVE_SA_EMAIL"
EOF
echo "✅ adk_agent/.env generated successfully!"

# Step 3: Set up Python Virtual Environment & Install Dependencies
echo ""
echo "================================================================="
echo "Step 3: Setting up Python virtual environment & dependencies..."
echo "================================================================="

# Detect compatible Python version (3.10 or 3.11)
PYTHON_BIN=""
if command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3.10 &>/dev/null; then
    PYTHON_BIN="python3.10"
elif command -v python3 &>/dev/null; then
    # Check if the default python3 is 3.10 or 3.11
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [ "$PY_VERSION" = "3.10" ] || [ "$PY_VERSION" = "3.11" ]; then
        PYTHON_BIN="python3"
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    # Fallback to default python3 with a gentle non-blocking note
    PYTHON_BIN="python3"
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "⚠️  Note: Vertex AI Reasoning Engine officially supports Python 3.10 or 3.11."
    echo "Your system is running Python $PY_VERSION. We will proceed using it, but if you encounter"
    echo "deployment failures (Error Code 13), we recommend installing Python 3.11 and re-running."
    echo ""
else
    echo "✅ Found compatible Python runtime: $PYTHON_BIN"
fi


# Clean up old incompatible venv if it exists
if [ -d "venv" ] && [ -z "$FORCE_PY" ]; then
    # Verify if the existing venv matches our target python version
    VENV_PY_VER=$(venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")
    TARGET_PY_VER=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [ "$VENV_PY_VER" != "$TARGET_PY_VER" ]; then
        echo "Recreating virtual environment because Python version changed ($VENV_PY_VER -> $TARGET_PY_VER)..."
        rm -rf venv
    fi
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment 'venv' using $PYTHON_BIN..."
    $PYTHON_BIN -m venv venv
fi


echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip -q

echo "Installing ADK and agent requirements..."
# Combine into a single command to ensure pip resolves dependencies consistently for both
pip install "google-adk[gcp]" -r adk_agent/requirements.txt -q
echo "✅ Dependencies installed successfully!"


# Step 4: Deploy the Agent using ADK
echo ""
echo "================================================================="
echo "Step 4: Deploying Slide Gen Agent to Vertex AI Agent Engine..."
echo "================================================================="
cd adk_agent
# Stream the deployment logs in real-time while capturing them to a temp file
adk deploy agent_engine \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$REGION" \
  --display_name="slide-gen-agent" \
  --artifact_service_uri="gs://$BUCKET_NAME" \
  . 2>&1 | tee deploy_output.log

# Capture the exit code of the adk deploy command (not the tee command)
ADK_EXIT_CODE=${PIPESTATUS[0]}

# Double-Check: Verify if the deployment was TRULY successful by scanning the logs
if [ $ADK_EXIT_CODE -ne 0 ] || grep -q "Deploy failed" deploy_output.log || grep -q "Failed to deploy" deploy_output.log || ! grep -q "reasoningEngines" deploy_output.log; then
    echo ""
    echo "❌ Error: Slide Gen Agent deployment failed!"
    echo "Please review the deployment logs printed above or check Cloud Build for more details."
    rm -f deploy_output.log
    exit 1
fi

# Clean up temporary log file on success
rm -f deploy_output.log

# Print Post-Deployment Walkthrough
echo ""
echo "================================================================="
echo "🎉 Slide Gen Agent Deployed Successfully!"
echo "================================================================="

echo ""
echo "Please complete the following two manual steps to activate:"
echo ""
echo "1. Enable Google Workspace Domain-Wide Delegation:"
echo "   -----------------------------------------------"
echo "   This allows the agent to upload slides directly to your users' Google Drives."
echo "   "
echo "   - Log in to Google Workspace Admin Console (https://admin.google.com)"
echo "   - Go to Security -> API controls -> Domain-wide delegation."
echo "   - Click 'Add new' and enter:"
echo "     * Client ID: $DRIVE_SA_CLIENT_ID"
echo "     * OAuth scopes: https://www.googleapis.com/auth/drive.file"
echo "   - Click 'Authorise'."
echo ""
echo "2. Connect to Gemini Enterprise Admin Console:"
echo "   -------------------------------------------"
echo "   - Log in to your Gemini Enterprise Admin Console."
echo "   - Navigate to 'Agents' in the left sidebar."
echo "   - Click '+ Add Agent' and select 'Custom agent via Agent Engine'."
echo "   - Enter the Reasoning Engine Resource ID printed by the ADK deploy command above"
echo "     (e.g., projects/$GOOGLE_CLOUD_PROJECT/locations/$REGION/reasoningEngines/...)"
echo "   - Complete the IAM permission configuration to secure the connection."
echo "================================================================="
