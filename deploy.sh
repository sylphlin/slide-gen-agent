#!/bin/bash
set -e

GE_APP_ID=""
POSITIONAL=()
for arg in "$@"; do
  case $arg in
    --ge=*) GE_APP_ID="${arg#*=}" ;;
    --ge) GE_APP_ID="__NEXT__" ;;
    *)
      if [ "$GE_APP_ID" = "__NEXT__" ]; then
        GE_APP_ID="$arg"
      else
        POSITIONAL+=("$arg")
      fi
      ;;
  esac
done

if [ -n "$GE_APP_ID" ]; then
  GE_APP_ID="${GE_APP_ID%/}"
fi

PROJECT_ID="${POSITIONAL[0]:?Usage: bash deploy.sh <PROJECT_ID> [REGION] [--ge APP_ID]}"
REGION="${POSITIONAL[1]:-us-central1}"

SA_NAME="slide-gen-agent-runtime"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER=$(gcloud config get-value account 2>/dev/null)

echo "Deploying AI Slide Deck & Speaker Script Generator to project: $PROJECT_ID (region: $REGION)"
[ -n "$GE_APP_ID" ] && echo "  + Gemini Enterprise registration (APP_ID: $GE_APP_ID)"

gcloud config set project "$PROJECT_ID" --quiet

gcloud services enable iam.googleapis.com --project="$PROJECT_ID" --quiet

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="AI Slide Deck & Speaker Script Generator runtime" --project="$PROJECT_ID"
fi

for role in roles/aiplatform.user roles/serviceusage.serviceUsageConsumer roles/logging.logWriter; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" --role="$role" --condition=None --quiet 2>/dev/null || true
done

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --member="serviceAccount:${SA_EMAIL}" --role=roles/iam.serviceAccountTokenCreator \
    --project="$PROJECT_ID" 2>/dev/null || true

if [ -n "$DEPLOYER" ]; then
    gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
        --member="user:${DEPLOYER}" --role=roles/iam.serviceAccountUser \
        --project="$PROJECT_ID" 2>/dev/null || true
fi

# Setup GCP resources
if [ -f setup.sh ]; then
    bash setup.sh "$PROJECT_ID" "$REGION"
fi

BUCKET_NAME="slide-gen-sessions-${PROJECT_ID}"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="serviceAccount:${SA_EMAIL}" --role=roles/storage.objectAdmin 2>/dev/null || true

# Prepare env vars
IMAGE_LOCATION="${IMAGE_LOCATION:-global}"
TEXT_MODEL="${TEXT_MODEL:-gemini-3.5-flash}"
IMAGE_MODEL="${IMAGE_MODEL:-gemini-3.1-flash-image}"
THINKING_LEVEL="${THINKING_LEVEL:-high}"
THINKING_BUDGET="${THINKING_BUDGET:-2048}"
DRIVE_FOLDER_NAME="${DRIVE_FOLDER_NAME:-slide-gen-agent}"

UPDATE_ENV_VARS="IMAGE_LOCATION=${IMAGE_LOCATION},TEXT_MODEL=${TEXT_MODEL},IMAGE_MODEL=${IMAGE_MODEL},THINKING_LEVEL=${THINKING_LEVEL},THINKING_BUDGET=${THINKING_BUDGET},DRIVE_FOLDER_NAME=${DRIVE_FOLDER_NAME}"
if [ -n "$DRIVE_SA_EMAIL" ]; then
    UPDATE_ENV_VARS="${UPDATE_ENV_VARS},DRIVE_SA_EMAIL=${DRIVE_SA_EMAIL}"
fi

export PATH="$HOME/.local/bin:$PATH"

# Install & deploy
if [ -d .venv ]; then
    .venv/bin/pip install google-agents-cli
    AGENTS_CLI=".venv/bin/agents-cli"
else
    uv pip install google-agents-cli 2>/dev/null || pip install --user google-agents-cli 2>/dev/null || pip install google-agents-cli
    if [ -f "$HOME/.local/bin/agents-cli" ]; then
        AGENTS_CLI="$HOME/.local/bin/agents-cli"
    elif command -v agents-cli &>/dev/null; then
        AGENTS_CLI="$(command -v agents-cli)"
    else
        AGENTS_CLI="agents-cli"
    fi
fi

DEPLOY_OUTPUT=$(GOOGLE_CLOUD_PROJECT="$PROJECT_ID" GOOGLE_CLOUD_LOCATION="$REGION" \
  IMAGE_LOCATION="$IMAGE_LOCATION" TEXT_MODEL="$TEXT_MODEL" IMAGE_MODEL="$IMAGE_MODEL" THINKING_LEVEL="$THINKING_LEVEL" THINKING_BUDGET="$THINKING_BUDGET" DRIVE_FOLDER_NAME="$DRIVE_FOLDER_NAME" \
  $AGENTS_CLI deploy --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA_EMAIL" \
  --update-env-vars "$UPDATE_ENV_VARS" \
  2>&1 | tee /dev/stderr) || true

REASONING_ENGINE_ID=$(echo "$DEPLOY_OUTPUT" | grep -oP 'reasoningEngines/\K\d+' | tail -1)
echo "Agent Engine deployment complete!"
[ -n "$REASONING_ENGINE_ID" ] && echo "  Reasoning Engine ID: $REASONING_ENGINE_ID"

# GE registration
if [ -n "$GE_APP_ID" ] && [ -n "$REASONING_ENGINE_ID" ]; then
    echo "Registering agent to Gemini Enterprise..."
    
    # If GE_APP_ID was passed as boolean/flag only (--ge without value), auto-detect the GE app ID
    if [ "$GE_APP_ID" = "__NEXT__" ] || [ "$GE_APP_ID" = "true" ]; then
        DETECTED_GE_APP=$($AGENTS_CLI publish gemini-enterprise --list --project "$PROJECT_ID" 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('apps', [{}])[0].get('name', ''))" 2>/dev/null || true)
        if [ -n "$DETECTED_GE_APP" ]; then
            GE_APP_ID="$DETECTED_GE_APP"
        fi
    fi

    PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null || echo "")
    RUNTIME_RESOURCE_ID="projects/${PROJECT_NUM}/locations/${REGION}/reasoningEngines/${REASONING_ENGINE_ID}"
    
    $AGENTS_CLI publish gemini-enterprise --project "$PROJECT_ID" \
        --gemini-enterprise-app-id "$GE_APP_ID" \
        --agent-runtime-id "$RUNTIME_RESOURCE_ID" || true
elif [ -n "$GE_APP_ID" ] && [ -z "$REASONING_ENGINE_ID" ]; then
    echo "Skipping GE registration (Agent Engine deploy failed — no Reasoning Engine ID)"
fi

echo "Deployment complete!"
