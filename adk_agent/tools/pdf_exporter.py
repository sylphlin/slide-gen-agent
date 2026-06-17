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

# Inject skills/slide-gen-agent/scripts into sys.path to resolve pdf_exporter
tools_dir = os.path.dirname(os.path.abspath(__file__))

# Try packaging context first: [tools_dir]/../skills/slide-gen-agent/scripts
skills_scripts_dir = os.path.abspath(os.path.join(tools_dir, '..', 'skills', 'slide-gen-agent', 'scripts'))
if not os.path.exists(skills_scripts_dir):
    # Fall back to repo root: [tools_dir]/../../skills/slide-gen-agent/scripts
    skills_scripts_dir = os.path.abspath(os.path.join(tools_dir, '..', '..', 'skills', 'slide-gen-agent', 'scripts'))

if skills_scripts_dir not in sys.path:
    sys.path.insert(0, skills_scripts_dir)

from pdf_exporter import export_session_to_pdf


async def export_deck_pdf(session_path: str, tool_context: ToolContext) -> str:
    """Compiles all generated slide PNG images in the active session into a single PDF document.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    slug = get_topic_slug(session_path)
    pdf_filename = f"{slug}.pdf"
    
    try:
        # Call the core, self-contained export function from the skill folder
        result = export_session_to_pdf(session_path, pdf_filename)
        pdf_path = result["pdfPath"]
        
        # Read the generated PDF bytes to save as artifact
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
            
        artifact_part = Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        version = await save_artifact_helper(pdf_filename, artifact_part, tool_context)

        gcs_url = get_gcs_artifact_url(pdf_filename, tool_context, version=version)
        if gcs_url:
            return f"Presentation PDF successfully compiled.\nDownload it here: {gcs_url}"

        return f"Presentation PDF successfully compiled and saved to {pdf_path}"
    except Exception as e:
        return f"Failed to export PDF: {str(e)}"

