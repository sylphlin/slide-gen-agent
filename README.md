# Slide Gen Agent

[English (en)](README.md) | [繁體中文 (zh-TW)](README.zh-TW.md) | [简体中文 (zh-CN)](README.zh-CN.md) | [日本語 (ja)](README.ja.md) | [한국어 (ko)](README.ko.md)

`slide-gen-agent` is a conversational slide deck generator — just chat with the agent to turn any source material (articles, reports, outlines, raw notes) into a complete, visually polished presentation. Describe what you want, review the output, and refine it through natural conversation until the deck is exactly right.

**Key capabilities:**
- **Conversational & iterative** — tell the agent to adjust a slide's content, swap a color, or restructure the entire outline mid-session. Changes are applied surgically without regenerating the whole deck.
- **Speaker scripts included** — every slide comes with a full 1–2 minute spoken script, written as natural presenter delivery. Scripts are embedded in the PPTX notes section and included in the preview page, so you walk into the room prepared.
- **Multilingual** — supports 100+ languages including Chinese (Traditional & Simplified), English, Japanese, Korean, Thai, Vietnamese, and other Asian scripts for both slide content and speaker notes. Export to PDF via browser print to preserve system fonts without server-side font dependencies.
- **Production-ready exports** — download as PPTX (with editable speaker notes), PDF slides, browser-printed speaker-notes PDF, or push directly to **Google Slides** for instant in-browser presentation and sharing (with editable speaker notes).

This repository is structured to support three progressive deployment and usage methods, ranging from lightweight prompt-based skills to production-grade enterprise agents.

---

## 📖 Core Design Philosophy & Logic

Traditional AI slide generators create layouts and visuals in a single black-box step, which often results in inconsistent designs, random formatting, and crude iteration — tweaking a single slide's structure or integrating revised speaker content typically requires regenerating the entire deck.

`slide-gen-agent` uses a **decoupled, six-stage pipeline** with plain-text intermediate files as the backbone. Every design decision lives in an editable Markdown file — so you can refine any layer (global style, slide structure, or per-slide content) through chat, and only the affected slides get regenerated.

```mermaid
graph TD
    A[Source Material] --> A0(Stage 0: Clarification & Alignment)
    A0 -->|User Confirms Context| B(Stage 1: Content Analysis & Proposal)
    B -->|User Approves| C[Create isolated Workspace Session]
    C --> D(Stage 2: Structured Markdown Generation)

    D -->|Step 1| E1[design.md - Brand System]
    D -->|Step 2| E2[outlines.md - Slide Outlines]
    E2 -->|Step 3: Guides Content Routing| E3[slide_xx.md - Script + Optional Layout]

    E1 & E3 --> F(Stage 3: Image Generation)
    F -->|Generates| G1[slide_xx.png - Slide Images]
    G1 --> H(Stage 4: Review & Iterate)
    H -->|Compiles| G2[preview.html - Presentation Preview]

    H -->|Script or Layout Changes| E3
    H -->|Outline / Order Changes| E2
    H -->|Brand / Color Changes| E1

    H -->|User Approves| I(Stage 5: Packaging & Download)
    I -->|Option 1| J[topic.pptx - Widescreen PPTX with Speaker Notes]
    I -->|Option 2| K[topic.pdf - PDF Slides Only]
    I -->|Option 3| L[preview.html → Browser Print-to-PDF with Speaker Notes]
    I -->|Option 4| M[Google Slides - Direct Drive Upload & Share]
```

### The Six-Stage Pipeline

0. **Stage 0: Clarification & Alignment**
   - Before touching the source material, the agent confirms three core context elements: **expected presentation duration** (or slide count), **target audience**, and **expected goal/outcome**.
   - *The agent pauses and waits for you.* If any of these are missing from your initial request, it will ask before proceeding.

1. **Stage 1: Content Analysis & Proposal**
   - The agent reads your source material (documents, transcripts, raw notes) to understand the domain, tone, and target audience.
   - It proposes a **slide count**, **design theme**, and **hex-code color palette**.
   - *The agent pauses and waits for you.* You can accept the proposal or adjust the theme/color palette.

2. **Stage 2: Structured Markdown Generation**
   - Once approved, the agent generates three types of Markdown files in an isolated session folder:
     - **`design.md`**: The brand system — hex color palette, typography, spacing, and visual style rules. This is the SSoT for brand consistency across all slides.
     - **`outlines.md`**: Complete slide list with layout type and 2–3 sentence summary per slide.
     - **`slide_xx.md`**: Per-slide file with title, speaker script (260–300 words), and an optional `## Layout` section (left empty on first pass — the image model infers a suitable composition from the slide type and script).
   - *The pipeline flows directly into Stage 3 without pausing.*

3. **Stage 3: Image Generation**
   - The agent combines `design.md` (brand) and `slide_xx.md` (per-slide spec) into a structured prompt for each slide.
   - It sends this to the image generation model to produce the final 16:9 high-fidelity PNG (`slide_xx.png`).
   - *The pipeline flows directly into Stage 4.*

4. **Stage 4: Review & Iterate**
   - The agent compiles all slide images and speaker notes into a `preview.html` page, and presents the preview link and slide images in the chat.
   - *The agent pauses and waits for your feedback.*
   - Tell the agent what to change in plain language. Changes are applied surgically — only the affected slides are regenerated:
     - Script or layout edits → update the relevant `slide_xx.md` + regenerate that slide only
     - Slide reorder / add / delete → update `outlines.md` + affected `slide_xx.md` files (including Transition & Hook rewrites) + regenerate only the changed slides
     - Brand / color change → update `design.md` + regenerate all slides
   - The loop repeats until you explicitly approve all slides.

5. **Stage 5: Presentation Packaging & Download**
   - Once you approve the final slides, the agent offers four export options:
     - **Google Slides**: The agent uploads the PPTX to Google Drive as a Google Slides file in the `slide-gen-agent` folder and shares it with you as editor. Opens directly in Google Slides for immediate presentation and sharing. *(Note: Slide layouts are rendered as high-quality, static images, while speaker notes in the notes section remain fully editable. Requires Google Drive API enabled in GCP and Domain-Wide Delegation configured in Google Workspace Admin.)*
     - **PPTX (PowerPoint with Speaker Notes)**: A widescreen PowerPoint file featuring slide images, with speaker notes fully editable in the PowerPoint notes section of each slide. Filename uses the presentation topic (e.g. `ai-trends-2025.pptx`).
     - **PDF: Slides**: A PDF compiled from all slide images (perfect for presenting directly). Filename uses the presentation topic (e.g. `ai-trends-2025.pdf`).
     - **PDF: Speaker Notes**: Open the `preview.html` link and click the **"Save as PDF"** button. The browser renders each slide and its notes as a clean, paginated PDF using your local system fonts — this correctly handles all languages including CJK and Southeast Asian scripts without any server-side font dependencies.

---

## 🛠️ Directory Structure

```text
slide-gen-agent/
├── README.md                # Project overview and setup (this file)
├── deploy.sh                # Interactive orchestration script for automated deployment
├── deploy/
│   └── terraform/           # Terraform configurations for provisioning GCP resources
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── skills/
│   └── slide-gen-agent/     # 🌟 Standard self-contained Agent Skill (for Antigravity/Codex)
│       ├── SKILL.md         # Playbook/guidelines (YAML frontmatter + instructions)
│       ├── assets/          # Static templates used by the skill
│       │   ├── design.md    # Brand system template (colors, typography, visual style)
│       │   ├── outlines.md  # Deck outline template
│       │   └── slide_xx.md  # Per-slide template (title, optional layout, script)
│       └── scripts/         # Custom tools bundled with the skill
│           ├── pdf_exporter.py # Widescreen presentation PDF compiler
│           ├── pptx_exporter.py # Widescreen PPTX compiler with speaker notes
│           ├── notes_pdf_exporter.py # Renders a PDF combining slide images and speaker notes
│           └── preview_generator.py # HTML preview page compiler (includes Save as PDF)
└── adk_agent/               # Programmatic Host Agent (Python ADK 2.0 implementation)
    ├── requirements.txt     # Python dependency configuration (includes python-pptx & reportlab)
    ├── agent.py             # Main agent entry point
    ├── config.py            # Environment and agent configuration manager
    └── tools/               # Agent tools
        ├── __init__.py
        ├── file_manager.py  # Session initialization and file writer tools
        ├── image_generation.py # Gemini slide image generator tool
        ├── pdf_exporter.py  # Pillow-based widescreen PDF exporter
        ├── pptx_exporter.py # PowerPoint widescreen (PPTX) with speaker notes exporter
        ├── notes_pdf_exporter.py # Renders a PDF combining slide images and speaker notes
        ├── drive_exporter.py # Google Drive upload → Google Slides converter & sharer
        └── preview_generator.py # HTML slide preview and notes compiler (includes Save as PDF)
```

---

## 🚀 Installation & Deployment Guide

Select the installation method that fits your target environment:

### 🔹 Method 1: Universal Agent Skill (`SKILL.md`)
This is a pure prompt/guideline-based installation, requiring no code hosting.
* **Use Case**: Agent Platforms that support Agent Skills, provide a sandboxed code-execution environment, and have text-to-image generation capabilities (e.g., Antigravity, Codex).
* **How to Install**:
  1. Copy the entire `skills/slide-gen-agent/` directory into your Agent Platform's skills folder. This ensures the platform has access to the core playbook (`SKILL.md`), the static templates in `assets/`, and the custom execution scripts in `scripts/` (e.g., PPTX and PDF compilers).
  2. Register and enable the skill in your Agent Platform.

---

### 🔹 Method 2: Gemini Enterprise
This method deploys the agent as a Vertex AI Reasoning Engine and connects it to Gemini Enterprise.

#### Option 1: One-Click Installation (Recommended)
We provide an automated, production-ready deployment suite using **Terraform** and a companion **orchestration script** (`deploy.sh`). This completely automates enabling APIs, creating Google Drive delegation Service Accounts, provisioning GCS session buckets, configuring complex IAM role bindings, setting up the Python virtual environment, and registering the agent in Vertex AI.

> [!NOTE]
> For a detailed, step-by-step breakdown of the prerequisites, interactive configurations, and execution stages performed by the script, see the [Deployment Script Details](deploy_details.md) guide.


##### 1. Prerequisites
We **highly recommend** deploying directly from **[Google Cloud Shell](https://shell.cloud.google.com)**. It is a free, pre-configured browser-based terminal with all necessary tools pre-installed.

* **If using Google Cloud Shell (Recommended)**:
  - All tools (`gcloud` and `terraform`) are pre-installed.
  - You only need to authorize Application Default Credentials (ADC) in the shell:
    ```bash
    gcloud auth application-default login
    ```

* **If using your Local Machine**:
  - You must install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) and the [Terraform CLI](https://developer.hashicorp.com/terraform/downloads).
  - You must authenticate both your gcloud CLI and Application Default Credentials (ADC):
    ```bash
    gcloud auth login
    gcloud auth application-default login
    ```

##### 2. Run the Deployment
Open your terminal (or Google Cloud Shell) and run the following commands to clone the repository and launch the interactive deployment script:
```bash
git clone https://github.com/sylphlin/slide-gen-agent
cd slide-gen-agent
./deploy.sh
```

The script will guide you through:
1. **Interactive Configuration**: Confirms your target GCP Project ID and Region.
2. **Infrastructure Provisioning**: Executes Terraform to configure APIs, IAM permissions, GCS buckets, and Service Accounts.
3. **Environment Setup**: Generates `adk_agent/.env` with your project configurations.
4. **Agent Packaging & Deployment**: Installs python dependencies and uses the ADK CLI to package and register the agent as a Vertex AI Reasoning Engine.

When finished, the script will output your **Reasoning Engine Resource ID** (e.g., `projects/{PROJECT_NUMBER}/locations/{REGION}/reasoningEngines/{ENGINE_ID}`).

##### 3. Post-Deployment Configuration
To complete the integration, perform these two manual steps:

###### A. Configure Google Workspace Domain-Wide Delegation
This allows the agent to upload slides directly to your users' Google Drives:
1. Go to the [Google Workspace Admin Console](https://admin.google.com).
2. Navigate to **Security → Access and data Control → API Control → Domain-wide delegation**.
3. Click **Add new** and enter:
   - **Client ID**: The OAuth2 Client ID of the Drive SA (this will be printed at the end of the `deploy.sh` script, or can be found in the Terraform outputs).
   - **OAuth scopes**: `https://www.googleapis.com/auth/drive.file`
4. Click **Authorise**.

###### B. Connect to Gemini Enterprise
1. Log in to the **Gemini Enterprise Admin Console**.
2. Navigate to **Agents** in the left sidebar.
3. Click **+ Add Agent**.
4. Select **Custom agent via Agent Engine** and paste the **Reasoning Engine Resource ID** printed by the script.
5. Configure IAM authentication permissions to secure the connection.

---

#### Option 2: Manual Installation

> [!IMPORTANT]
> If you have already deployed the agent using **Option 1: One-Click Installation (Recommended)**, you can completely skip this manual installation section.
If your organization's policies restrict the use of Terraform, or if you prefer to provision GCP resources manually using the `gcloud` CLI, you can follow these step-by-step instructions.

##### Part A — One-Time Project Setup
Do this once per GCP project. You won't need to repeat these steps for future updates.

###### 1. Enable GCP APIs
Enable the following required APIs in your GCP project:
- [Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com)
- [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
- [Cloud Build API](https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com)
- [Artifact Registry API](https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com)

###### 2. Configure IAM Permissions

Reasoning Engine runs your code under the Google-managed **Vertex AI Reasoning Engine service agent** (`service-{PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com`). This SA handles model calls but cannot be directly registered for Google Workspace Domain-Wide Delegation. For Google Drive export, you must create a separate user-managed SA (`slide-gen-drive`) that the runtime SA is authorized to impersonate.

Run the following commands in your terminal (replace `your-actual-gcp-project-id` with your project ID):

```bash
export GOOGLE_CLOUD_PROJECT="your-actual-gcp-project-id"

PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")

# Runtime SA: Google-managed identity that runs your agent code
RUNTIME_SA="service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"

# Build SA: Used during 'adk deploy' for container image building and logs
BUILD_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# 1. Create the Drive Service Account
gcloud iam service-accounts create slide-gen-drive \
  --display-name="Slide Gen Drive Exporter" \
  --project=$GOOGLE_CLOUD_PROJECT

DRIVE_SA="slide-gen-drive@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

# 2. Grant Vertex AI access to the Runtime SA
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/aiplatform.user"

# 3. Grant GCS bucket access to the Runtime SA
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/storage.objectUser"

# 4. Grant Build SA logging and container registry access
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/artifactregistry.writer"

# 5. Allow Runtime SA to impersonate the Drive SA (sign JWTs)
# Note: The direction is critical. The role is bound ON the Drive SA resource.
gcloud iam service-accounts add-iam-policy-binding $DRIVE_SA \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=$GOOGLE_CLOUD_PROJECT
```

###### 3. Create a Cloud Storage Bucket
Create a private GCS bucket in your target region to store session artifacts:
```bash
gcloud storage buckets create gs://slide-gen-sessions-your-actual-gcp-project-id --location=us-central1
```

###### 4. Configure Domain-Wide Delegation (Google Workspace Admin)
1. Go to the [Google Workspace Admin Console](https://admin.google.com).
2. Navigate to **Security → Access and data Control → API Control → Domain-wide delegation**.
3. Click **Add new** and enter:
   - **Client ID**: The OAuth2 Client ID of the `slide-gen-drive` SA. You can find it on the IAM Service Accounts page in the GCP Console under the **Details** tab.
   - **OAuth scopes**: `https://www.googleapis.com/auth/drive.file`
4. Click **Authorise**.

##### Part B — Install & Deploy
Repeat these steps whenever you want to update the agent code.

###### 1. Prepare Local Environment & Dependencies
From the root `slide-gen-agent` directory:
```bash
python3 -m venv venv
source venv/bin/activate
pip install "google-adk[gcp]" -r adk_agent/requirements.txt
```

###### 2. Configure Environment Variables
Create a `.env` file inside the `adk_agent` directory to store the target project ID:
```bash
cat > adk_agent/.env <<EOF
GOOGLE_CLOUD_PROJECT="your-actual-gcp-project-id"
DRIVE_SA_EMAIL="slide-gen-drive@your-actual-gcp-project-id.iam.gserviceaccount.com"
EOF
```

###### 3. Deploy to Vertex AI
Run the ADK deployer from the `adk_agent` directory:
```bash
cd adk_agent
adk deploy agent_engine \
  --project=your-actual-gcp-project-id \
  --region=us-central1 \
  --display_name="slide-gen-agent" \
  --artifact_service_uri="gs://slide-gen-sessions-your-actual-gcp-project-id" \
  .
```
*Take note of the resulting **Reasoning Engine Resource ID**.*

###### 4. Connect to Gemini Enterprise
1. Log in to the **Gemini Enterprise Admin Console**.
2. Navigate to **Agents** -> **+ Add Agent**.
3. Select **Custom agent via Agent Engine** and paste the **Reasoning Engine Resource ID**.
4. Configure IAM authentication permissions to secure the connection.