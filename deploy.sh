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
    PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
    ACCESS_TOKEN=$(gcloud auth print-access-token)

    AGENT_NAME="$(basename $(pwd))"
    if command -v python3 &>/dev/null && [ -f agent.yaml ]; then
        DISPLAY_NAME=$(python3 -c "
import yaml
d = yaml.safe_load(open('agent.yaml'))
dn = d.get('displayName', {})
print(dn.get('en', dn) if isinstance(dn, dict) else dn)
" 2>/dev/null || echo "$AGENT_NAME")
        AGENT_DESC=$(python3 -c "
import yaml
d = yaml.safe_load(open('agent.yaml'))
desc = d.get('description', {})
print(desc.get('en', desc) if isinstance(desc, dict) else desc)
" 2>/dev/null || echo "$AGENT_NAME")
    else
        DISPLAY_NAME="$AGENT_NAME"
        AGENT_DESC="$AGENT_NAME"
    fi

    if [[ "$GE_APP_ID" == */reasoningEngines/* ]]; then
        DETECTED_GE_APP=$($AGENTS_CLI publish gemini-enterprise --list --project "$PROJECT_ID" 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('apps', [{}])[0].get('name', ''))" 2>/dev/null || true)
        if [ -n "$DETECTED_GE_APP" ]; then
            GE_APP_ID="$DETECTED_GE_APP"
        fi
    fi

    if [[ "$GE_APP_ID" == projects/* ]]; then
        GE_API_URL="https://discoveryengine.googleapis.com/v1alpha/${GE_APP_ID}/assistants/default_assistant/agents"
    elif [[ "$GE_APP_ID" == collections/* ]]; then
        GE_API_URL="https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_NUM}/locations/global/${GE_APP_ID}/assistants/default_assistant/agents"
    elif [[ "$GE_APP_ID" == engines/* ]]; then
        GE_API_URL="https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_NUM}/locations/global/collections/default_collection/${GE_APP_ID}/assistants/default_assistant/agents"
    else
        GE_API_URL="https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_NUM}/locations/global/collections/default_collection/engines/${GE_APP_ID}/assistants/default_assistant/agents"
    fi

    REGISTER_RESPONSE=$(curl -s -X POST \
      "$GE_API_URL" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${PROJECT_NUM}" \
      -d "{
        \"displayName\": \"${DISPLAY_NAME}\",
        \"description\": \"${AGENT_DESC}\",
        \"icon\": {
          \"uri\": \"https://fonts.gstatic.com/s/i/short-term/release/googlesymbols/smart_toy/default/24px.svg\"
        },
        \"adk_agent_definition\": {
          \"tool_settings\": { \"tool_description\": \"${AGENT_DESC}\" },
          \"provisioned_reasoning_engine\": {
            \"reasoning_engine\": \"projects/${PROJECT_NUM}/locations/${REGION}/reasoningEngines/${REASONING_ENGINE_ID}\"
          }
        }
      }")

    if echo "$REGISTER_RESPONSE" | grep -q '"name"'; then
        echo "Gemini Enterprise registration successful!"
    else
        echo "Gemini Enterprise registration failed:"
        echo "$REGISTER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REGISTER_RESPONSE"
    fi
elif [ -n "$GE_APP_ID" ] && [ -z "$REASONING_ENGINE_ID" ]; then
    echo "Skipping GE registration (Agent Engine deploy failed — no Reasoning Engine ID)"
fi

echo "Deployment complete!"
