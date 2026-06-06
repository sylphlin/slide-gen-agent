import os
import glob
import re
import json
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper, get_gcs_artifact_url
except ImportError:
    from config import save_artifact_helper, get_gcs_artifact_url


def get_image_src(png_file: str, pad_num: str, tool_context) -> str:
    """Returns a GCS URL in Agent Engine, or a relative file path for local preview."""
    if os.environ.get('GOOGLE_CLOUD_AGENT_ENGINE_ID'):
        version = tool_context.state.get(f"slide_{pad_num}_gcs_version", 0)
        return get_gcs_artifact_url(f"slide_{pad_num}.png", tool_context, version=version)
    # Local: preview.html sits at session root, images are in slides/
    return f"./slides/{os.path.basename(png_file)}"

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
        
        # Get image source (GCS URL in Agent Engine, relative path locally)
        image_src = get_image_src(png_file, pad_num, tool_context)

        # Extract script notes
        md_file = os.path.join(session_path, f"slide_{pad_num}.md")
        script_notes = extract_script(md_file)

        # Format HTML block
        slide_items_html.append(f"""
        <div class="slide-container">
            <h3>Slide {pad_num}</h3>
            <img src="{image_src}" alt="Slide {pad_num}">
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
        .print-btn {{
            position: sticky;
            top: 16px;
            align-self: flex-end;
            margin-bottom: 8px;
            padding: 10px 20px;
            background: #007bff;
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            z-index: 100;
        }}
        .print-btn:hover {{ background: #0056b3; }}
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
        @media print {{
            .print-btn {{ display: none; }}
            h1 {{ display: none; }}
            body {{ background: white; padding: 0; margin: 0; display: block; }}
            .slide-container {{
                page-break-after: always;
                break-after: always;
                height: 100vh;
                box-shadow: none;
                border-radius: 0;
                border: none;
                margin: 0;
                padding: 12px;
                width: 100%;
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }}
            .speaker-notes {{
                flex: 1;
                overflow: hidden;
            }}
        }}
    </style>
</head>
<body>
    <button class="print-btn" onclick="window.print()">⬇ Save as PDF (with Speaker Notes)</button>
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
    version = await save_artifact_helper('preview.html', artifact_part, tool_context)

    try:
        from ..config import get_gcs_artifact_url
    except ImportError:
        from config import get_gcs_artifact_url

    gcs_url = get_gcs_artifact_url('preview.html', tool_context, version=version)
    if gcs_url:
        return f"Preview page successfully generated.\nView it here: {gcs_url}"
        
    return f"Preview page successfully generated at {preview_path}"
