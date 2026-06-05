import os

CONFIG = {
    # GCP Credentials & Locations
    'GOOGLE_CLOUD_PROJECT': os.environ.get('GOOGLE_CLOUD_PROJECT'),
    'GOOGLE_CLOUD_LOCATION': os.environ.get('GOOGLE_CLOUD_LOCATION') or 'global',
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
    cwd = os.getcwd()
    adk_agent_dir = cwd if cwd.endswith('adk-agent') else os.path.join(cwd, 'adk-agent')
    os.environ['SESSION_OUTPUT_DIR'] = os.path.join(adk_agent_dir, 'artifacts')

# Force Gen AI SDK to use Vertex AI mode
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'true'

# Inject credentials/locations into os.environ to auto-configure @google/genai SDK
if CONFIG['GOOGLE_CLOUD_PROJECT']:
    os.environ['GOOGLE_CLOUD_PROJECT'] = CONFIG['GOOGLE_CLOUD_PROJECT']
os.environ['GOOGLE_CLOUD_LOCATION'] = CONFIG['GOOGLE_CLOUD_LOCATION']
os.environ['IMAGEN_LOCATION'] = CONFIG['IMAGEN_LOCATION']
