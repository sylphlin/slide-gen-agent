import os
import glob
from PIL import Image
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper
except ImportError:
    from config import save_artifact_helper


async def export_deck_pdf(session_path: str, tool_context: ToolContext) -> str:
    """Compiles all generated slide PNG images in the active session into a single PDF document.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    # Search in 'slides/' subfolder first
    slides_dir = os.path.join(session_path, 'slides')
    png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
    
    # Fallback to session root directory if subfolder is empty
    if not png_files:
        slides_dir = session_path
        png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
        
    pdf_path = os.path.join(session_path, 'presentation.pdf')
    
    if not png_files:
        return "Error: No slide PNG images found in the session. Generate images first."
        
    try:
        # Load and convert images to RGB (PDF requires RGB format in Pillow)
        images = [Image.open(f).convert('RGB') for f in png_files]
        
        # Save as PDF
        # The first image acts as the base, and the rest are appended as extra pages
        images[0].save(
            pdf_path,
            save_all=True,
            append_images=images[1:]
        )
        
        # Read the generated PDF bytes to save as artifact
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
            
        artifact_part = Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        await save_artifact_helper('presentation.pdf', artifact_part, tool_context)
        
        try:
            from ..config import get_gcs_artifact_url
        except ImportError:
            from config import get_gcs_artifact_url
            
        gcs_url = get_gcs_artifact_url('presentation.pdf', tool_context)
        if gcs_url:
            return f"Presentation PDF successfully compiled.\nDownload it here: {gcs_url}"
            
        return f"Presentation PDF successfully compiled and saved to {pdf_path}"
    except Exception as e:
        return f"Failed to export PDF: {str(e)}"
