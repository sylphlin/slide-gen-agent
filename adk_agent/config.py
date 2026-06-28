import os
import sys


def _resolve_project_id() -> str | None:
    """Resolves the GCP project ID (string form, e.g. 'my-project', as required
    to construct service account emails like slide-gen-drive@{project_id}...).

    Auto-detection (ADC, metadata server) proved unreliable across runtime
    contexts — each returns a different wrong value (numeric project NUMBER,
    or an unrelated tenant project ID) depending on where the agent is hosted.
    So GOOGLE_CLOUD_PROJECT must be set explicitly (e.g. via a deployed .env
    file — see README) and is trusted as-is.
    """
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print("[config] Warning: GOOGLE_CLOUD_PROJECT is not set. Set it via the "
              "GOOGLE_CLOUD_PROJECT environment variable or a .env file in adk_agent/ "
              "(see README) — it cannot be reliably auto-detected at runtime.", file=sys.stderr)
    return project_id


CONFIG = {
    # GCP Credentials & Locations
    'GOOGLE_CLOUD_PROJECT': _resolve_project_id(),
    'GOOGLE_CLOUD_LOCATION': 'global',
    'IMAGE_LOCATION': os.environ.get('IMAGE_LOCATION') or 'global',

    # Model selection
    'TEXT_MODEL': os.environ.get('TEXT_MODEL') or 'gemini-3.5-flash',
    'IMAGE_MODEL': os.environ.get('IMAGE_MODEL') or 'gemini-3.1-flash-image',

    # Thinking settings
    'THINKING_LEVEL': os.environ.get('THINKING_LEVEL') or 'high',
    'THINKING_BUDGET': int(os.environ.get('THINKING_BUDGET') or '2048'),

    # Google Drive export (requires Domain-Wide Delegation)
    'DRIVE_FOLDER_NAME': os.environ.get('DRIVE_FOLDER_NAME') or 'slide-gen-agent',
    # Dedicated user-managed SA for DWD signJwt. Defaults to the standard naming
    # convention (slide-gen-drive@{PROJECT_ID}.iam.gserviceaccount.com) so no
    # extra env var is needed as long as the SA was created with that name.
    'DRIVE_SA_EMAIL': os.environ.get('DRIVE_SA_EMAIL'),
}

# Set output session directory in the environment for tools to use if not set.
if not os.environ.get('SESSION_OUTPUT_DIR'):
    # Detect if we are running inside the deployed Agent Engine container
    if 'AGENT_ENGINE_ID' in os.environ:
        os.environ['SESSION_OUTPUT_DIR'] = '/tmp/artifacts'
    else:
        cwd = os.getcwd()
        adk_agent_dir = cwd if cwd.endswith('adk_agent') else os.path.join(cwd, 'adk_agent')
        os.environ['SESSION_OUTPUT_DIR'] = os.path.join(adk_agent_dir, 'artifacts')

# Force Gen AI SDK to use Vertex AI mode
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'

# Inject credentials/locations into os.environ to auto-configure @google/genai SDK
if CONFIG['GOOGLE_CLOUD_PROJECT']:
    os.environ['GOOGLE_CLOUD_PROJECT'] = CONFIG['GOOGLE_CLOUD_PROJECT']
os.environ['GOOGLE_CLOUD_LOCATION'] = CONFIG['GOOGLE_CLOUD_LOCATION']
os.environ['IMAGE_LOCATION'] = CONFIG['IMAGE_LOCATION']

def get_gcs_artifact_url(filename: str, tool_context, version: int = 0) -> str:
    """Helper to generate the authenticated Cloud Storage link for an artifact inside Agent Engine."""
    import os
    if 'AGENT_ENGINE_ID' in os.environ:
        service = getattr(tool_context._invocation_context, 'artifact_service', None)
        if service and hasattr(service, 'bucket_name'):
            bucket = service.bucket_name
            session_id = tool_context.session.id
            app_name = tool_context._invocation_context.app_name or 'adk_agent'
            user_id = tool_context._invocation_context.user_id or 'vais-query-reasoning-engine'
            import time
            cb = int(time.time())
            # GCS Artifact service saves as {app_name}/{user_id}/{session_id}/{filename}/{version}
            # We append a cache-busting query parameter (?cb=timestamp) to force the browser to load the freshest version.
            return f"https://storage.cloud.google.com/{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}?cb={cb}"
    return ""

async def save_artifact_helper(filename: str, artifact, tool_context) -> int:
    """Saves an artifact. If running inside Agent Engine container, saves silently without adding to event actions to avoid raw UI attachments."""
    import os
    if 'AGENT_ENGINE_ID' in os.environ:
        service = getattr(tool_context._invocation_context, 'artifact_service', None)
        if service:
            return await service.save_artifact(
                app_name=tool_context._invocation_context.app_name,
                user_id=tool_context._invocation_context.user_id,
                session_id=tool_context.session.id,
                filename=filename,
                artifact=artifact,
            )
    return await tool_context.save_artifact(filename, artifact)


def read_gcs_versions(session_id: str) -> dict:
    """Reads the persistent GCS versions map for a session from the GCS bucket."""
    import os
    if 'AGENT_ENGINE_ID' not in os.environ:
        return {}
    import json
    try:
        from google.cloud import storage
        client = storage.Client()
        project_id = CONFIG['GOOGLE_CLOUD_PROJECT']
        bucket_name = f"slide-gen-sessions-{project_id}"
        bucket = client.bucket(bucket_name)
        blob_path = f"gcs_versions/{session_id}.json"
        blob = bucket.blob(blob_path)
        if blob.exists():
            data = blob.download_as_text()
            return json.loads(data)
    except Exception as e:
        import sys
        sys.stderr.write(f"⚠️ [read_gcs_versions] Warning: Failed to read versions from GCS: {e}\n")
        sys.stderr.flush()
    return {}


def write_gcs_versions(session_id: str, versions: dict):
    """Writes the persistent GCS versions map for a session to the GCS bucket."""
    import os
    if 'AGENT_ENGINE_ID' not in os.environ:
        return
    import json
    try:
        from google.cloud import storage
        client = storage.Client()
        project_id = CONFIG['GOOGLE_CLOUD_PROJECT']
        bucket_name = f"slide-gen-sessions-{project_id}"
        bucket = client.bucket(bucket_name)
        blob_path = f"gcs_versions/{session_id}.json"
        blob = bucket.blob(blob_path)
        blob.upload_from_string(json.dumps(versions, indent=2), content_type='application/json')
    except Exception as e:
        import sys
        sys.stderr.write(f"⚠️ [write_gcs_versions] Warning: Failed to write versions to GCS: {e}\n")
        sys.stderr.flush()


