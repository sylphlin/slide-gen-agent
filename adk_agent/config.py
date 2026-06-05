import os

CONFIG = {
    # GCP Credentials & Locations
    'GOOGLE_CLOUD_PROJECT': os.environ.get('GOOGLE_CLOUD_PROJECT'),
    'GOOGLE_CLOUD_LOCATION': 'global',
    'IMAGEN_LOCATION': os.environ.get('IMAGEN_LOCATION'),

    # Model selection
    'TEXT_MODEL': os.environ.get('TEXT_MODEL') or 'gemini-3.5-flash',
    'IMAGEN_MODEL': os.environ.get('IMAGEN_MODEL') or 'gemini-3.1-flash-image',

    # Thinking settings
    'THINKING_LEVEL': os.environ.get('THINKING_LEVEL') or 'high',
    'THINKING_BUDGET': int(os.environ.get('THINKING_BUDGET') or '2048'),
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

def get_gcs_artifact_url(filename: str, tool_context) -> str:
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
            # The initial version is always 0.
            return f"https://storage.cloud.google.com/{bucket}/{app_name}/{user_id}/{session_id}/{filename}/0"
    return ""

