import os
import re
import json
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper
except ImportError:
    from config import save_artifact_helper


def get_topic_slug(session_path: str) -> str:
    """Reads the Topic field from outlines.md and returns a filename-safe slug.
    Falls back to the session folder name if the Topic field is not found."""
    outlines_path = os.path.join(session_path, 'outlines.md')
    if os.path.exists(outlines_path):
        with open(outlines_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'\*\*Topic\*\*:\s*(.+)', content)
        if match:
            topic = match.group(1).strip()
            slug = re.sub(r'[^\w\s-]', '', topic)
            slug = re.sub(r'[\s_]+', '-', slug).strip('-').lower()
            return slug[:60] if slug else 'presentation'
    # Fallback: derive from session folder name (session_{project_name}_{timestamp})
    folder = os.path.basename(session_path)
    match = re.match(r'session_(.+)_\d{12}$', folder)
    if match:
        return match.group(1)
    return 'presentation'


def initialize_session(project_name: str) -> str:
    """Initializes a new slide deck session. Creates a dedicated folder and returns its absolute path.
    ALWAYS call this first before writing any slide files.
    
    Args:
        project_name: A short name for the presentation (e.g. tech-trends)
    """
    clean_name = re.sub(r'[^a-z0-9-_]', '-', project_name.lower())
    # Node.js used 12-char timestamp: YYYYMMDDHHMM
    # In python: %Y%m%d%H%M
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    session_id = f"session_{clean_name}_{timestamp}"
    
    base_output_dir = os.environ.get('SESSION_OUTPUT_DIR') or os.path.join(os.getcwd(), 'artifacts')
    session_path = os.path.abspath(os.path.join(base_output_dir, session_id))
    
    os.makedirs(os.path.join(session_path, 'slides'), exist_ok=True)
    
    return json.dumps({
        'message': 'Session successfully initialized.',
        'sessionId': session_id,
        'sessionPath': session_path
    })

async def save_design_spec(session_path: str, design_spec_content: str, tool_context: ToolContext) -> str:
    """Saves the customized design.md style specifications to the active session directory.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        design_spec_content: The full Markdown design specification details
        tool_context: The tool context injected by the framework
    """
    file_path = os.path.join(session_path, 'design.md')
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(design_spec_content)
        
    # Save as artifact
    artifact_part = Part.from_text(text=design_spec_content)
    await save_artifact_helper('design.md', artifact_part, tool_context)
    
    return f"Design specification successfully written to {file_path}"

async def save_outlines(session_path: str, outlines_content: str, tool_context: ToolContext) -> str:
    """Saves the complete outlines.md file to the active session directory.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        outlines_content: The full Markdown outline containing the slide table, types, and summaries
        tool_context: The tool context injected by the framework
    """
    file_path = os.path.join(session_path, 'outlines.md')
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(outlines_content)
        
    artifact_part = Part.from_text(text=outlines_content)
    await save_artifact_helper('outlines.md', artifact_part, tool_context)
    
    return f"Deck outlines successfully written to {file_path}"

async def save_slide_script(
    session_path: str,
    slide_number: int,
    slide_type: str,
    title: str,
    script: str,
    tool_context: ToolContext,
    layout: str = '',
) -> str:
    """Saves an individual slide script (slide_xx.md) with transition and spoken script content.

    Args:
        session_path: The absolute session path returned by initialize_session
        slide_number: The 1-indexed slide number (e.g. 1, 2, 3)
        slide_type: Layout type of the slide (e.g. Cover, Section Header, Two-Column, Data & Stat)
        title: The slide header/title text to render on the image
        script: The 260-300 word (EN) or 320-400 character (CJK) spoken script
        tool_context: The tool context injected by the framework
        layout: Optional visual layout override. Leave empty on first generation.
                Fill in only when the user requests a specific composition change.
    """
    pad_num = f"{slide_number:02d}"
    file_name = f"slide_{pad_num}.md"
    file_path = os.path.join(session_path, file_name)

    layout_section = f"\n## Layout\n\n{layout.strip()}\n" if layout and layout.strip() else "\n## Layout\n\n"

    file_content = f"""---
slide_number: {slide_number}
slide_type: "{slide_type}"
---

# {title}
{layout_section}
## Script

{script}
"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
        
    artifact_part = Part.from_text(text=file_content)
    await save_artifact_helper(file_name, artifact_part, tool_context)
    
    return f"Slide {pad_num} script successfully written to {file_path}"


async def save_user_asset(
    session_path: str,
    filename: str,
    file_content_b64: str,
    tool_context: ToolContext
) -> str:
    """Saves a user-provided asset (such as a QR code, logo, or screenshot) to the session directory
    so it can be overlaid onto slides.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        filename: The name of the file to save (e.g. qrcode.png)
        file_content_b64: The base64-encoded file content
        tool_context: The tool context injected by the framework
    """
    import base64
    file_path = os.path.join(session_path, filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        file_bytes = base64.b64decode(file_content_b64)
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        
        # Save as artifact
        artifact_part = Part.from_bytes(data=file_bytes, mime_type="image/png")
        await save_artifact_helper(filename, artifact_part, tool_context)
        
        return f"Asset successfully saved to {file_path}"
    except Exception as e:
        return f"Failed to save asset: {str(e)}"

