import os
import base64
from google import genai
from google.genai import types
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper
except ImportError:
    from config import save_artifact_helper


try:
    from ..config import CONFIG
except ImportError:
    from config import CONFIG

async def generate_slide_image(
    session_path: str,
    slide_number: int,
    tool_context: ToolContext
) -> str:
    """Reads design.md and slide_xx.md from the active session, merges them into a visual prompt,
    and generates the slide image using either Gemini or Vertex AI Imagen.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        slide_number: The 1-indexed slide number to generate the image for
        tool_context: The tool context injected by the framework
    """
    pad_num = f"{slide_number:02d}"
    file_name = f"slide_{pad_num}.png"
    file_path = os.path.join(session_path, 'slides', file_name)
    
    design_path = os.path.join(session_path, 'design.md')
    slide_path = os.path.join(session_path, f"slide_{pad_num}.md")
    
    # Validation
    if not os.path.exists(design_path):
        return f"Error: Missing design specification: {design_path}. Generate and save design.md first."
    if not os.path.exists(slide_path):
        return f"Error: Missing slide content file: {slide_path}. Generate and save slide_{pad_num}.md first."
        
    try:
        with open(design_path, 'r', encoding='utf-8') as f:
            design_content = f.read()
        with open(slide_path, 'r', encoding='utf-8') as f:
            slide_content = f.read()
    except Exception as e:
        return f"Failed to read session Markdown files: {str(e)}"
        
    # Construct merged XML-style prompt as defined in slide-gen-agent SKILL.md
    prompt = f"""Generate a professional 16:9 widescreen (1920×1080 px) presentation slide image based on the design system and slide content below.
- **DO** render the "Title" text from <slide_content> clearly on the slide, respecting the layout, typography, and colors defined in <design_system>.
- **DO NOT** render the "Script" text literally; use it only as contextual inspiration to generate the background illustration or visual elements.

<design_system>
{design_content}
</design_system>

<slide_content>
{slide_content}
</slide_content>"""

    # Initialize genai client.
    # In Reasoning Engine, this automatically uses default credentials and Vertex AI routing.
    client = genai.Client()
    
    is_gemini_image_model = CONFIG['IMAGEN_MODEL'].startswith('gemini-')
    print(f"DEBUG [generate_slide_image] IMAGEN_MODEL: {CONFIG['IMAGEN_MODEL']}, is_gemini: {is_gemini_image_model}")
    
    try:
        if is_gemini_image_model:
            # Gemini image models must be called via generate_content with response_modalities
            response = client.models.generate_content(
                model=CONFIG['IMAGEN_MODEL'],
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"]
                )
            )
            
            # Extract image parts
            parts = response.candidates[0].content.parts
            image_part = None
            for part in parts:
                if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                    image_part = part
                    break
            
            if not image_part:
                return f"Failed to generate image for Slide {pad_num}: No image bytes returned in Gemini response."
            
            # Handle both base64 string and raw bytes (depends on REST vs gRPC transport)
            raw_data = image_part.inline_data.data
            if isinstance(raw_data, str):
                image_bytes = base64.b64decode(raw_data)
            else:
                image_bytes = raw_data
        else:
            # Traditional Imagen models must be called via generate_images
            result = client.models.generate_images(
                model=CONFIG['IMAGEN_MODEL'],
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type='image/png',
                    aspect_ratio='16:9',
                )
            )
            image_bytes = result.generated_images[0].image.image_bytes
            
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
            
        # Save as artifact and record the GCS version in session state
        artifact_part = Part.from_bytes(data=image_bytes, mime_type="image/png")
        version = await save_artifact_helper(f"slide_{pad_num}.png", artifact_part, tool_context)
        tool_context.state[f"slide_{pad_num}_gcs_version"] = version

        return f"Image for slide {pad_num} successfully generated and written to {file_path}"
    except Exception as e:
        return f"Failed to generate image for Slide {pad_num}: {str(e)}"
