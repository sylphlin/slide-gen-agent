import os
from google import genai
from google.genai import types
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part
from config import CONFIG

async def generate_slide_image(
    session_path: str,
    slide_number: int,
    prompt: str,
    tool_context: ToolContext
) -> str:
    """Generates a slide image using Imagen 3 based on a detailed text prompt.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        slide_number: The 1-indexed slide number (e.g. 1, 2, 3)
        prompt: Detailed visual prompt describing slide contents, layouts, and colors
        tool_context: The tool context injected by the framework
    """
    pad_num = f"{slide_number:02d}"
    file_name = f"slide_{pad_num}.png"
    file_path = os.path.join(session_path, 'slides', file_name)
    
    # Initialize genai client.
    # In Reasoning Engine, this automatically uses default credentials and Vertex AI routing.
    client = genai.Client()
    
    # Generate image
    result = client.models.generate_images(
        model=CONFIG['IMAGEN_MODEL'],
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            output_mime_type='image/png',
            aspect_ratio='16:9',
        )
    )
    
    # Extract image bytes
    image_bytes = result.generated_images[0].image.image_bytes
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(image_bytes)
        
    # Save as artifact (using binary bytes part)
    artifact_part = Part.from_bytes(data=image_bytes, mime_type="image/png")
    await tool_context.save_artifact(f"slide_{pad_num}.png", artifact_part)
    
    return f"Image for slide {pad_num} successfully generated and written to {file_path}"
