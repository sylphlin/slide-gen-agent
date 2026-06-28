import os
import sys
import glob
from PIL import Image
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper, get_gcs_artifact_url
    from ..tools.file_manager import get_topic_slug
except ImportError:
    from config import save_artifact_helper, get_gcs_artifact_url
    from tools.file_manager import get_topic_slug


def export_session_to_pdf(session_path: str, pdf_file_name: str = None) -> dict:
    """Gathers all slide PNGs and compiles them into a single PDF presentation."""
    slides_dir = os.path.join(session_path, 'slides')
    png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
    
    if not png_files:
        slides_dir = session_path
        png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
        
    if not png_files:
        raise ValueError(f"No slide PNG images found in {session_path}. Make sure to generate slide images first.")
        
    images = [Image.open(f).convert('RGB') for f in png_files]
    
    output_name = pdf_file_name or 'presentation.pdf'
    if not output_name.endswith('.pdf'):
        output_name += '.pdf'
        
    output_path = os.path.join(session_path, output_name)
    
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:]
    )
    
    return {
        "message": f"Successfully compiled {len(png_files)} slides into a single PDF presentation.",
        "pdfName": output_name,
        "pdfPath": output_path
    }


async def export_deck_pdf(session_path: str, tool_context: ToolContext) -> str:
    """Compiles all generated slide PNG images in the active session into a single PDF document.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    slug = get_topic_slug(session_path)
    pdf_filename = f"{slug}.pdf"
    
    try:
        result = export_session_to_pdf(session_path, pdf_filename)
        pdf_path = result["pdfPath"]
        
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
