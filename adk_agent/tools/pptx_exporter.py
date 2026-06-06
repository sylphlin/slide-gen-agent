import os
import glob
import re
from pptx import Presentation
from pptx.util import Inches
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper
except ImportError:
    from config import save_artifact_helper


def extract_script(md_path: str) -> str:
    """Extracts the speaker notes from the ## Script section of the slide's markdown file."""
    if not os.path.exists(md_path):
        return ""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'## Script\s*([\s\S]*)', content)
    if match:
        return match.group(1).strip()
    return ""


async def export_deck_pptx(session_path: str, tool_context: ToolContext) -> str:
    """Compiles all generated slide PNG images in the active session into a single PPTX presentation,
    attaching the corresponding speaker notes to each slide.
    
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
        
    pptx_path = os.path.join(session_path, 'presentation.pptx')
    
    if not png_files:
        return "Error: No slide PNG images found in the session. Generate images first."
        
    try:
        prs = Presentation()
        # Set slide dimensions to widescreen 16:9 (13.333" x 7.5")
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        
        # Use a blank slide layout (usually index 6 in the default template)
        blank_layout = prs.slide_layouts[6]
        
        for png_file in png_files:
            filename = os.path.basename(png_file)
            slide_num_match = re.search(r'slide_(\d+)\.png', filename)
            if not slide_num_match:
                continue
            pad_num = slide_num_match.group(1)
            
            # Extract script notes
            md_file = os.path.join(session_path, f"slide_{pad_num}.md")
            script_notes = extract_script(md_file)
            
            # Add a new blank slide
            slide = prs.slides.add_slide(blank_layout)
            
            # Add image covering the entire slide
            slide.shapes.add_picture(
                png_file, 
                Inches(0), 
                Inches(0), 
                width=prs.slide_width, 
                height=prs.slide_height
            )
            
            # Add speaker notes if they exist
            if script_notes:
                notes_slide = slide.notes_slide
                text_frame = notes_slide.notes_text_frame
                text_frame.text = script_notes
                
        prs.save(pptx_path)
        
        # Read the generated PPTX bytes to save as artifact
        with open(pptx_path, 'rb') as f:
            pptx_bytes = f.read()
            
        artifact_part = Part.from_bytes(
            data=pptx_bytes, 
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        await save_artifact_helper('presentation.pptx', artifact_part, tool_context)
        
        try:
            from ..config import get_gcs_artifact_url
        except ImportError:
            from config import get_gcs_artifact_url
            
        gcs_url = get_gcs_artifact_url('presentation.pptx', tool_context)
        if gcs_url:
            return f"Presentation PPTX successfully compiled with speaker notes.\nDownload it here: {gcs_url}"
            
        return f"Presentation PPTX successfully compiled and saved to {pptx_path}"
    except Exception as e:
        return f"Failed to export PPTX: {str(e)}"
