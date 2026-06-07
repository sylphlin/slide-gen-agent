import os
import sys


def _resolve_project_id() -> str | None:
    """Resolves the GCP project ID (string form, e.g. 'my-project', as required
    to construct service account emails like slide-gen-drive@{project_id}...).

    Prefers the GOOGLE_CLOUD_PROJECT env var (explicit override for local dev),
    then queries the GCE/Agent Engine metadata server's project-id endpoint
    directly. google.auth.default()'s project_id is intentionally NOT used here:
    under some Agent Engine runtime credential contexts it returns the numeric
    project NUMBER instead of the string project ID, producing a malformed,
    non-existent service account email.

    A purely-numeric GOOGLE_CLOUD_PROJECT value is distrusted and skipped: real
    project IDs always start with a lowercase letter and never look like a bare
    number, but some managed runtimes (e.g. Agent Engine) auto-inject this env
    var set to the numeric project NUMBER, which would otherwise short-circuit
    straight to the same malformed-email bug we're fixing here.
    """
    env_project = os.environ.get('GOOGLE_CLOUD_PROJECT')
    if env_project and not env_project.isdigit():
        return env_project
    try:
        import urllib.request
        req = urllib.request.Request(
            'http://metadata.google.internal/computeMetadata/v1/project/project-id',
            headers={'Metadata-Flavor': 'Google'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode()
    except Exception as e:
        print(f"[config] Warning: Could not resolve a project ID from the "
              f"GOOGLE_CLOUD_PROJECT env var or the metadata server ({e}). "
              "Set the GOOGLE_CLOUD_PROJECT environment variable explicitly.", file=sys.stderr)
        return None


CONFIG = {
    # GCP Credentials & Locations
    'GOOGLE_CLOUD_PROJECT': _resolve_project_id(),
    'GOOGLE_CLOUD_LOCATION': 'global',
    'IMAGEN_LOCATION': os.environ.get('IMAGEN_LOCATION'),

    # Model selection
    'TEXT_MODEL': os.environ.get('TEXT_MODEL') or 'gemini-3.5-flash',
    'IMAGEN_MODEL': os.environ.get('IMAGEN_MODEL') or 'gemini-3.1-flash-image',

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

# Normalize and auto-fill image generation endpoint location
if not CONFIG['IMAGEN_LOCATION']:
    is_global_imagen = CONFIG['IMAGEN_MODEL'].startswith('gemini-')
    CONFIG['IMAGEN_LOCATION'] = 'us-central1' if (CONFIG['GOOGLE_CLOUD_LOCATION'] == 'global' and not is_global_imagen) else CONFIG['GOOGLE_CLOUD_LOCATION']

# Set output session directory in the environment for tools to use if not set.
if not os.environ.get('SESSION_OUTPUT_DIR'):
    # Detect if we are running inside the deployed Agent Engine container
    if 'GOOGLE_CLOUD_AGENT_ENGINE_ID' in os.environ:
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
os.environ['IMAGEN_LOCATION'] = CONFIG['IMAGEN_LOCATION']

def get_gcs_artifact_url(filename: str, tool_context, version: int = 0) -> str:
    """Helper to generate the authenticated Cloud Storage link for an artifact inside Agent Engine."""
    import os
    if 'GOOGLE_CLOUD_AGENT_ENGINE_ID' in os.environ:
        service = getattr(tool_context._invocation_context, 'artifact_service', None)
        if service and hasattr(service, 'bucket_name'):
            bucket = service.bucket_name
            session_id = tool_context.session.id
            app_name = tool_context._invocation_context.app_name or 'adk_agent'
            user_id = tool_context._invocation_context.user_id or 'vais-query-reasoning-engine'
            # GCS Artifact service saves as {app_name}/{user_id}/{session_id}/{filename}/{version}
            return f"https://storage.cloud.google.com/{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}"
    return ""

async def save_artifact_helper(filename: str, artifact, tool_context) -> int:
    """Saves an artifact. If running inside Agent Engine container, saves silently without adding to event actions to avoid raw UI attachments."""
    import os
    if 'GOOGLE_CLOUD_AGENT_ENGINE_ID' in os.environ:
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

