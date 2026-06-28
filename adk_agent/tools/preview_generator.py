import os
import sys
import glob
import re
import base64
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper, get_gcs_artifact_url
except ImportError:
    from config import save_artifact_helper, get_gcs_artifact_url


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
        
    match = re.search(r'## Script\s*([\s\S]*)', content)
    if match:
        return match.group(1).strip()
    return "(No script content found)"


def generate_preview_page_core(session_path: str) -> str:
    """Generates an HTML preview page listing all generated slide PNGs and notes."""
    slides_dir = os.path.join(session_path, 'slides')
    png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
    
    if not png_files:
        slides_dir = session_path
        png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
        
    if not png_files:
        return 'No slide PNG images found to preview.'
        
    cards_html = ''
    for png_file in png_files:
        filename = os.path.basename(png_file)
        slide_num_match = re.search(r'slide_(\d+)\.png', filename)
        if not slide_num_match:
            continue
        pad_num = slide_num_match.group(1)
        
        image_base64 = get_base64_image(png_file)
        
        md_path = os.path.join(session_path, f"slide_{pad_num}.md")
        script_notes = extract_script(md_path)
        
        formatted_script = ""
        if script_notes and script_notes != "(No script content found)":
            formatted_script = "\n".join(
                f"<p>{line.strip()}</p>" 
                for line in script_notes.split('\n') 
                if line.strip()
            )
            
        notes_html = f"""
        <div class="slide-notes">
          <div class="notes-label">🗣️ Speaker Notes:</div>
          <div class="notes-content">{formatted_script}</div>
        </div>""" if formatted_script else ""
        
        cards_html += f"""
    <div class="slide-card">
      <div class="slide-header">Slide {pad_num}</div>
      <img class="slide-img" src="{image_base64}" alt="Slide {pad_num}">
      {notes_html}
    </div>"""
        
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation Deck Preview</title>
  <style>
    body {{
      font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: #f8f9fa;
      color: #202124;
      margin: 0;
      padding: 40px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    h1 {{
      margin-bottom: 30px;
      font-size: 28px;
      font-weight: 500;
    }}
    .deck-container {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 45px;
      width: 100%;
      max-width: 960px;
    }}
    .slide-card {{
      background: #ffffff;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
      width: 100%;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .slide-header {{
      font-size: 16px;
      font-weight: 500;
      color: #5f6368;
      margin-bottom: 4px;
      border-bottom: 1px solid #f1f3f4;
      padding-bottom: 8px;
    }}
    .slide-img {{
      width: 100%;
      height: auto;
      aspect-ratio: 16/9;
      border: 1px solid #e8eaed;
      border-radius: 4px;
      display: block;
    }}
    .slide-notes {{
      background-color: #f1f3f4;
      border-left: 4px solid #1a73e8;
      border-radius: 4px;
      padding: 14px 18px;
      text-align: left;
    }}
    .notes-label {{
      font-size: 13px;
      font-weight: 500;
      color: #1a73e8;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .notes-content {{
      font-size: 15px;
      line-height: 1.6;
      color: #3c4043;
    }}
    .notes-content p {{
      margin: 0 0 8px 0;
    }}
    .notes-content p:last-child {{
      margin-bottom: 0;
    }}
    .print-btn {{
      position: sticky;
      top: 16px;
      align-self: flex-end;
      margin-bottom: 8px;
      padding: 10px 20px;
      background: #1a73e8;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 14px;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(0,0,0,0.2);
      z-index: 100;
    }}
    .print-btn:hover {{ background: #1557b0; }}
    @media print {{
      .print-btn {{ display: none; }}
      h1 {{ display: none; }}
      body {{ background: white; padding: 0; margin: 0; display: block; }}
      .deck-container {{ gap: 0; }}
      .slide-card {{
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
      .slide-notes {{
        flex: 1;
        overflow: hidden;
      }}
    }}
  </style>
</head>
<body>
  <button class="print-btn" onclick="window.print()">⬇ Save as PDF (with Speaker Notes)</button>
  <h1>Presentation Deck Preview</h1>
  <div class="deck-container">{cards_html}
  </div>
</body>
</html>"""

    output_path = os.path.join(session_path, 'preview.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    return f"Successfully generated preview page: {output_path} (file name: preview.html)"


async def generate_preview_page(session_path: str, tool_context: ToolContext) -> str:
    """Creates a preview.html file inside the session directory displaying all generated slide images
    and their speaker notes in a clean layout.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    try:
        result_msg = generate_preview_page_core(session_path)
        
        preview_path = os.path.join(session_path, 'preview.html')
        if not os.path.exists(preview_path):
            return "Error: preview.html was not generated."
            
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
