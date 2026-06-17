import os
import sys
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper, get_gcs_artifact_url
    from ..tools.file_manager import get_topic_slug
except ImportError:
    from config import save_artifact_helper, get_gcs_artifact_url
    from tools.file_manager import get_topic_slug

# Inject skills/slide-gen-agent/scripts into sys.path to resolve pptx_exporter
tools_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(tools_dir, '..', '..'))
skills_scripts_dir = os.path.join(repo_root, 'skills', 'slide-gen-agent', 'scripts')
if skills_scripts_dir not in sys.path:
    sys.path.insert(0, skills_scripts_dir)

from pptx_exporter import export_session_to_pptx


async def export_deck_pptx(session_path: str, tool_context: ToolContext) -> str:
    """Compiles all generated slide PNG images in the active session into a single PPTX presentation,
    attaching the corresponding speaker notes to each slide.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    slug = get_topic_slug(session_path)
    pptx_filename = f"{slug}.pptx"
    
    try:
        # Call the core, self-contained export function from the skill folder
        result = export_session_to_pptx(session_path, pptx_filename)
        pptx_path = result["pptxPath"]
        
        # Read the generated PPTX bytes to save as artifact
        with open(pptx_path, 'rb') as f:
            pptx_bytes = f.read()
            
        artifact_part = Part.from_bytes(
            data=pptx_bytes,
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        version = await save_artifact_helper(pptx_filename, artifact_part, tool_context)

        gcs_url = get_gcs_artifact_url(pptx_filename, tool_context, version=version)
        if gcs_url:
            return f"Presentation PPTX successfully compiled with speaker notes.\nDownload it here: {gcs_url}"

        return f"Presentation PPTX successfully compiled and saved to {pptx_path}"
    except Exception as e:
        return f"Failed to export PPTX: {str(e)}"
