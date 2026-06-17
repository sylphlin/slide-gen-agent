import os
import sys
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper, get_gcs_artifact_url
except ImportError:
    from config import save_artifact_helper, get_gcs_artifact_url

# Inject skills/slide-gen-agent/scripts into sys.path to resolve preview_generator
tools_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(tools_dir, '..', '..'))
skills_scripts_dir = os.path.join(repo_root, 'skills', 'slide-gen-agent', 'scripts')
if skills_scripts_dir not in sys.path:
    sys.path.insert(0, skills_scripts_dir)

from preview_generator import generate_preview_page as generate_preview_page_core


async def generate_preview_page(session_path: str, tool_context: ToolContext) -> str:
    """Creates a preview.html file inside the session directory displaying all generated slide images
    and their speaker notes in a clean layout.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    try:
        # Call the core, self-contained preview generator from the skill folder
        result_msg = generate_preview_page_core(session_path)
        
        preview_path = os.path.join(session_path, 'preview.html')
        if not os.path.exists(preview_path):
            return "Error: preview.html was not generated."
            
        # Read the generated HTML bytes to save as artifact
        with open(preview_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        html_bytes = html_content.encode('utf-8')
        artifact_part = Part.from_bytes(data=html_bytes, mime_type="text/html")
        version = await save_artifact_helper('preview.html', artifact_part, tool_context)

        gcs_url = get_gcs_artifact_url('preview.html', tool_context, version=version)
        if gcs_url:
            return f"Preview page successfully generated.\nView it here: {gcs_url}"
            
        return f"Preview page successfully generated at {preview_path}"
    except Exception as e:
        return f"Failed to generate preview page: {str(e)}"
