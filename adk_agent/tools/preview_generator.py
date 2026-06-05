import os
import glob
import re
import base64
import json
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper
except ImportError:
    from config import save_artifact_helper


def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        data = f.read()
        encoded = base64.b64encode(data).decode('utf-8')
        return f"data:image/png;base64,{encoded}"

def extract_script(md_path: str) -> str:
    if not os.path.exists(md_path):
        return "(No script content found)"
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Extract ## Script section (non-greedy or matching till end/next header)
    match = re.search(r'## Script\s*([\s\S]*)', content)
    if match:
        return match.group(1).strip()
    return "(No script content found)"

async def generate_preview_page(session_path: str, tool_context: ToolContext) -> str:
    """Creates a preview.html file inside the session directory displaying all generated slide images
    and their speaker notes in a clean layout.
    
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
        
    preview_path = os.path.join(session_path, 'preview.html')
    
    if not png_files:
        return "Error: No slide PNG images found in the session. Generate images first."
        
    slide_items_html = []
    
    for png_file in png_files:
        filename = os.path.basename(png_file)
        slide_num_match = re.search(r'slide_(\d+)\.png', filename)
        if not slide_num_match:
            continue
        pad_num = slide_num_match.group(1)
        
        # Read image as base64
        image_base64 = get_base64_image(png_file)
        
        # Extract script notes
        md_file = os.path.join(session_path, f"slide_{pad_num}.md")
        script_notes = extract_script(md_file)
        
        # Format HTML block
        slide_items_html.append(f"""
        <div class="slide-container">
            <h3>Slide {pad_num}</h3>
            <img src="{image_base64}" alt="Slide {pad_num}">
            <div class="speaker-notes">
                <strong>Speaker Notes:</strong><br>
                {script_notes.replace(chr(10), '<br>')}
            </div>
        </div>
        """)
        
    slides_content_html = "\n".join(slide_items_html)
    
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Slide Presentation Preview</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        h1 {{
            color: #333;
        }}
        .slide-container {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            margin: 20px 0;
            padding: 20px;
            width: 800px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .slide-container img {{
            width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .speaker-notes {{
            margin-top: 15px;
            padding: 12px;
            background-color: #fafafa;
            border-left: 4px solid #007bff;
            width: 95%;
            font-size: 14px;
            color: #555;
            line-height: 1.5;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <h1>Presentation Slide Deck Preview</h1>
    {slides_content_html}
</body>
</html>
"""

    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write(html_template)
        
    html_bytes = html_template.encode('utf-8')
    artifact_part = Part.from_bytes(data=html_bytes, mime_type="text/html")
    await save_artifact_helper('preview.html', artifact_part, tool_context)
    
    try:
        from ..config import get_gcs_artifact_url
    except ImportError:
        from config import get_gcs_artifact_url
        
    gcs_url = get_gcs_artifact_url('preview.html', tool_context)
    if gcs_url:
        return f"Preview page successfully generated.\nView it here: {gcs_url}"
        
    return f"Preview page successfully generated at {preview_path}"
