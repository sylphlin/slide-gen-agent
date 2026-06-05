import os
import re
import json
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

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
    await tool_context.save_artifact('design.md', artifact_part)
    
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
    await tool_context.save_artifact('outlines.md', artifact_part)
    
    return f"Deck outlines successfully written to {file_path}"

async def save_slide_script(
    session_path: str, 
    slide_number: int, 
    slide_type: str, 
    title: str, 
    script: str, 
    tool_context: ToolContext
) -> str:
    """Saves an individual slide script (slide_xx.md) with transition and spoken script content.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        slide_number: The 1-indexed slide number (e.g. 1, 2, 3)
        slide_type: Layout type of the slide (e.g. Cover, Section Header, Two-Column, Data & Stat)
        title: The slide header/title text to render on the image
        script: The 150-300 character transition and spoken script
        tool_context: The tool context injected by the framework
    """
    pad_num = f"{slide_number:02d}"
    file_name = f"slide_{pad_num}.md"
    file_path = os.path.join(session_path, file_name)
    
    file_content = f"""---
slide_number: {slide_number}
slide_type: "{slide_type}"
---

# {title}

## Script

{script}
"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
        
    artifact_part = Part.from_text(text=file_content)
    await tool_context.save_artifact(file_name, artifact_part)
    
    return f"Slide {pad_num} script successfully written to {file_path}"
