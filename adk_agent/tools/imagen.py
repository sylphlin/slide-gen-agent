import os
import base64
import asyncio
import json
import re
from google import genai
from google.genai import types
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper, read_gcs_versions, write_gcs_versions
except ImportError:
    from config import save_artifact_helper, read_gcs_versions, write_gcs_versions


try:
    from ..config import CONFIG
except ImportError:
    from config import CONFIG

_RETRYABLE_PHRASES = (
    '429', 'resource exhausted', 'quota exceeded',
    'rate limit', 'too many requests', '503', 'service unavailable',
)


async def _call_with_retry(fn, max_retries: int = 4, initial_delay: float = 5.0):
    """Calls a synchronous API fn(), retrying on 429/ResourceExhausted/503 with exponential backoff."""
    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            err_str = str(e).lower()
            if attempt < max_retries and any(p in err_str for p in _RETRYABLE_PHRASES):
                import sys
                import json
                is_exhausted = "exhausted" in err_str or "429" in err_str or "quota" in err_str
                error_info = {
                    "error": {
                        "code": 429 if is_exhausted else 503,
                        "message": str(e),
                        "status": "RESOURCE_EXHAUSTED" if is_exhausted else "SERVICE_UNAVAILABLE",
                        "attempt": attempt + 1,
                        "max_retries": max_retries + 1,
                        "retry_delay_seconds": delay
                    }
                }
                sys.stderr.write(f"⚠️ [imagen] Retryable error (attempt {attempt + 1}/{max_retries + 1}): {str(e)[:120]}. Retrying in {delay:.0f}s...\n")
                sys.stderr.write(f"{json.dumps(error_info)}\n")
                sys.stderr.flush()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 120)
            else:
                raise


def parse_slide_frontmatter(slide_path: str) -> dict:
    import re
    metadata = {}
    if not os.path.exists(slide_path):
        return metadata
    try:
        with open(slide_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if match:
            frontmatter_text = match.group(1)
            for line in frontmatter_text.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    metadata[key] = val
    except Exception as e:
        print(f"Error parsing frontmatter: {e}")
    return metadata


def apply_overlay_to_slide(session_path: str, slide_number: int, slide_path: str, output_image_path: str):
    from PIL import Image, ImageDraw
    
    metadata = parse_slide_frontmatter(slide_path)
    qr_url = metadata.get('qr_overlay')
    image_overlay_file = metadata.get('image_overlay')
    
    # If neither overlay is specified, do nothing
    if not qr_url and not image_overlay_file:
        return
        
    overlay_img = None
    
    # If it's a Content (Overlay) slide, the AI already draws a gorgeous card container and label.
    # We do not need to draw a second card in Python. We just paste the QR Code/Image directly.
    is_overlay_slide = metadata.get('slide_type') == 'Content (Overlay)'
    draw_card = not is_overlay_slide and (qr_url is not None)
    
    if qr_url:
        try:
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=1,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            overlay_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        except Exception as e:
            print(f"Failed to generate QR code for {qr_url}: {e}")
            return
            
    elif image_overlay_file:
        paths_to_try = [
            os.path.join(session_path, 'slides', image_overlay_file),
            os.path.join(session_path, image_overlay_file),
            os.path.abspath(image_overlay_file),
        ]
        
        found_path = None
        for p in paths_to_try:
            if os.path.exists(p):
                found_path = p
                break
                
        if not found_path:
            print(f"Warning: Overlay image '{image_overlay_file}' not found in paths: {paths_to_try}")
            return
            
        try:
            overlay_img = Image.open(found_path).convert("RGBA")
            draw_card = False
        except Exception as e:
            print(f"Failed to open overlay image {found_path}: {e}")
            return
            
    if not overlay_img:
        return
        
    try:
        slide_img = Image.open(output_image_path).convert("RGBA")
        slide_w, slide_h = slide_img.size
        
        try:
            target_size = int(metadata.get('image_size', 220))
        except ValueError:
            target_size = 220
            
        orig_w, orig_h = overlay_img.size
        aspect_ratio = orig_h / orig_w
        new_w = target_size
        new_h = int(new_w * aspect_ratio)
        overlay_img = overlay_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        position = metadata.get('image_position', 'bottom-right').lower()
        
        if is_overlay_slide:
            # Under Content (Overlay), we align the overlay precisely inside the AI-generated card column.
            # Aspect Ratio is 1920x1080.
            # Left/Right columns are separated at ~65/35 split.
            # Vertical center is 540. We shift up by 25px to leave room for the AI-rendered label at the bottom.
            center_y = slide_h // 2
            
            if 'left' in position:
                # Left Column: x from 80 to 672 (center at 376)
                center_x = 80 + (672 - 80) // 2
                paste_x = center_x - new_w // 2
                paste_y = center_y - new_h // 2 - 25
            elif 'center' in position:
                # Centered: x center at 960, y center shifted down to 700
                center_x = slide_w // 2
                paste_x = center_x - new_w // 2
                paste_y = 700 - new_h // 2
            else:
                # Right Column (Default): x from 1248 to 1840 (center at 1544)
                center_x = 1248 + (1840 - 1248) // 2
                paste_x = center_x - new_w // 2
                paste_y = center_y - new_h // 2 - 25
        else:
            # Normal slide overlay with programmatic white card container
            padding = 15 if draw_card else 0
            card_w = new_w + 2 * padding
            card_h = new_h + 2 * padding
            margin = 80
            
            if position == 'bottom-left':
                card_x = margin
                card_y = slide_h - card_h - margin
            elif position == 'top-left':
                card_x = margin
                card_y = margin
            elif position == 'top-right':
                card_x = slide_w - card_w - margin
                card_y = margin
            elif position == 'center':
                card_x = (slide_w - card_w) // 2
                card_y = (slide_h - card_h) // 2
            else:
                card_x = slide_w - card_w - margin
                card_y = slide_h - card_h - margin
                
            if draw_card:
                draw = ImageDraw.Draw(slide_img)
                card_coords = [card_x, card_y, card_x + card_w, card_y + card_h]
                draw.rounded_rectangle(card_coords, radius=12, fill=(255, 255, 255, 255))
                draw.rounded_rectangle(card_coords, radius=12, outline=(220, 220, 220, 255), width=1)
                
            paste_x = card_x + padding
            paste_y = card_y + padding
            
        slide_img.paste(overlay_img, (paste_x, paste_y), mask=overlay_img)
        slide_img.convert("RGB").save(output_image_path, "PNG")
        print(f"Successfully applied overlay to {output_image_path}")
    except Exception as e:
        print(f"Error applying overlay to slide {slide_number}: {e}")


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

    prompt = f"""Generate a professional 16:9 widescreen (1920×1080 px) presentation slide image based on the brand system and slide specification below.
- **DO** render the "Title" from <slide_spec> clearly on the slide, applying the colors and typography defined in <brand_system>.
- **DO** follow the "## Layout" section in <slide_spec> precisely if it is present; otherwise infer an appropriate visual composition from the Slide Type and Script content.
- **DO NOT** render the "Script" text literally; use it only as contextual inspiration for background visuals and thematic elements.

<brand_system>
{design_content}
</brand_system>

<slide_spec>
{slide_content}
</slide_spec>"""

    # Initialize genai client.
    # In Reasoning Engine, this automatically uses default credentials and Vertex AI routing.
    client = genai.Client()
    
    is_gemini_image_model = CONFIG['IMAGEN_MODEL'].startswith('gemini-')

    try:
        if is_gemini_image_model:
            # Gemini image models must be called via generate_content with response_modalities
            response = await _call_with_retry(
                lambda: client.models.generate_content(
                    model=CONFIG['IMAGEN_MODEL'],
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    )
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
            result = await _call_with_retry(
                lambda: client.models.generate_images(
                    model=CONFIG['IMAGEN_MODEL'],
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type='image/png',
                        aspect_ratio='16:9',
                    )
                )
            )
            image_bytes = result.generated_images[0].image.image_bytes
            
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
            
        # Apply overlay (if any) to the file on disk
        apply_overlay_to_slide(session_path, slide_number, slide_path, file_path)
        
        # Read the (possibly modified) file back to get the final image bytes
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
            
        # Save as artifact and record the GCS version in session state
        artifact_part = Part.from_bytes(data=image_bytes, mime_type="image/png")
        version = await save_artifact_helper(f"slide_{pad_num}.png", artifact_part, tool_context)
        tool_context.state[f"slide_{pad_num}_gcs_version"] = version


        # 1. Local backup (useful for local development)
        versions_path = os.path.join(session_path, 'gcs_versions.json')
        local_versions = {}
        if os.path.exists(versions_path):
            try:
                with open(versions_path, 'r', encoding='utf-8') as f:
                    local_versions = json.load(f)
            except Exception:
                pass
        local_versions[f"slide_{pad_num}_gcs_version"] = version
        try:
            with open(versions_path, 'w', encoding='utf-8') as f:
                json.dump(local_versions, f, indent=2)
        except Exception:
            pass

        # 2. Global persistent GCS store (critical for cloud container restarts and distributed instances)
        session_id = tool_context.session.id
        gcs_versions = read_gcs_versions(session_id)
        gcs_versions[f"slide_{pad_num}_gcs_version"] = version
        write_gcs_versions(session_id, gcs_versions)

        return f"Image for slide {pad_num} successfully generated and written to {file_path}"
    except Exception as e:
        return f"Failed to generate image for Slide {pad_num}: {str(e)}"

async def generate_sequence_images(
    session_path: str,
    sequence_id: str,
    slide_numbers: list[int],
    tool_context: ToolContext
) -> str:
    """Generates multiple slide images in a single call to guarantee layout consistency across a sequence.
    Only supported by native multimodal Gemini models (not traditional Imagen).
    
    Args:
        session_path: The absolute session path
        sequence_id: The ID of the sequence
        slide_numbers: List of slide integers (e.g. [3, 4, 5])
        tool_context: Tool context
    """
    if not slide_numbers:
        return "Error: slide_numbers list is empty."

    design_path = os.path.join(session_path, 'design.md')
    if not os.path.exists(design_path):
        return f"Error: Missing design specification: {design_path}."

    try:
        with open(design_path, 'r', encoding='utf-8') as f:
            design_content = f.read()
    except Exception as e:
        return f"Failed to read design.md: {str(e)}"

    prompt = f"""Generate {len(slide_numbers)} professional 16:9 widescreen (1920×1080 px) presentation slide images based on the brand system and the slide specifications below.
You MUST output exactly {len(slide_numbers)} images in the exact order of the slide specifications. 
Because these slides form a continuous sequence (Sequence ID: {sequence_id}), you must ensure their overall visual layout structure, geometry, background, and styling are perfectly consistent across all {len(slide_numbers)} images. The only changes should be the text content and active highlights as specified.

<brand_system>
{design_content}
</brand_system>
"""

    for slide_number in slide_numbers:
        pad_num = f"{slide_number:02d}"
        slide_path = os.path.join(session_path, f"slide_{pad_num}.md")
        if not os.path.exists(slide_path):
            return f"Error: Missing slide content file: {slide_path}."
        try:
            with open(slide_path, 'r', encoding='utf-8') as f:
                slide_content = f.read()
        except Exception as e:
            return f"Failed to read {slide_path}: {str(e)}"
        
        prompt += f"\n<slide_spec index=\"{slide_number}\" original_file=\"slide_{pad_num}.md\">\n{slide_content}\n</slide_spec>\n"

    client = genai.Client()
    is_gemini_image_model = CONFIG['IMAGEN_MODEL'].startswith('gemini-')
    
    if not is_gemini_image_model:
        return "Error: generate_sequence_images requires a native Gemini multimodal model (like Gemini Flash 1.5/3.0+). Traditional Imagen models cannot generate multiple images per prompt."

    try:
        response = await _call_with_retry(
            lambda: client.models.generate_content(
                model=CONFIG['IMAGEN_MODEL'],
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                )
            )
        )

        image_parts = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                    image_parts.append(part)

        if not image_parts:
            return "Failed to generate sequence images: No image bytes returned in Gemini response."
        
        if len(image_parts) != len(slide_numbers):
            # We got a different number of images than requested. Try to save what we got anyway.
            # But we will return a warning.
            warning = f"Warning: Requested {len(slide_numbers)} images but model returned {len(image_parts)}. "
        else:
            warning = ""

        results = []
        session_id = tool_context.session.id
        gcs_versions = read_gcs_versions(session_id)

        for i, part in enumerate(image_parts):
            if i >= len(slide_numbers):
                break
            
            slide_number = slide_numbers[i]
            pad_num = f"{slide_number:02d}"
            file_path = os.path.join(session_path, 'slides', f"slide_{pad_num}.png")
            
            raw_data = part.inline_data.data
            image_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(image_bytes)
                
            # Apply overlay (if any) to the file on disk
            slide_path = os.path.join(session_path, f"slide_{pad_num}.md")
            apply_overlay_to_slide(session_path, slide_number, slide_path, file_path)
            
            # Read the (possibly modified) file back to get the final image bytes
            with open(file_path, 'rb') as f:
                image_bytes = f.read()

            artifact_part = Part.from_bytes(data=image_bytes, mime_type="image/png")
            version = await save_artifact_helper(f"slide_{pad_num}.png", artifact_part, tool_context)
            tool_context.state[f"slide_{pad_num}_gcs_version"] = version

            gcs_versions[f"slide_{pad_num}_gcs_version"] = version
            results.append(f"slide_{pad_num}.png saved")

        write_gcs_versions(session_id, gcs_versions)

        return warning + "Successfully generated and saved sequence images: " + ", ".join(results)

    except Exception as e:
        return f"Failed to generate sequence images: {str(e)}"
