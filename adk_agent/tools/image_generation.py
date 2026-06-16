import os
import re
import base64
import time
import asyncio
from google import genai
from google.genai import types
from google.adk.tools.tool_context import ToolContext

try:
    from ..config import CONFIG, save_artifact_helper, read_gcs_versions, write_gcs_versions
except ImportError:
    from config import CONFIG, save_artifact_helper, read_gcs_versions, write_gcs_versions


async def _call_with_retry(fn):
    """Executes a Gemini API call with automatic exponential backoff for 429 Rate Limit errors."""
    max_retries = 5
    base_delay = 2.0
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            err_msg = str(e).lower()
            is_429 = "429" in err_msg or "resource_exhausted" in err_msg or "resource exhausted" in err_msg
            if is_429 and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                import sys
                sys.stderr.write(f"⚠️ [Resilience] Imagen/Gemini API 429 Rate Limit hit in image_generation. Retrying in {delay:.1f}s...\n")
                sys.stderr.flush()
                await asyncio.sleep(delay)
            else:
                raise e


def parse_slide_frontmatter(slide_path: str) -> dict:
    """Parses the YAML frontmatter from a slide markdown file."""
    metadata = {}
    if not os.path.exists(slide_path):
        return metadata
    try:
        with open(slide_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                for line in frontmatter_text.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' in line:
                        key, val = line.split(':', 1)
                        metadata[key.strip()] = val.strip().strip('"').strip("'")
    except Exception as e:
        print(f"Error parsing frontmatter: {e}", flush=True)
    return metadata


def detect_placeholder_with_gemini(image_path: str, slide_w: int, slide_h: int) -> tuple[int, int, int, int] | None:
    """Uses Gemini Multimodal Vision to detect the exact bounding box of the QR code/placeholder on the slide.
    Returns (left, top, w, h) in slide pixel dimensions, or None if detection fails."""
    try:
        import os
        from google import genai
        from google.genai import types
        import re
        
        # Initialize Gen AI Client
        client = genai.Client()
        
        # Load the image bytes
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png"
        )
        
        # Use the text model bound to the system
        model_name = os.environ.get('TEXT_MODEL') or 'gemini-3.5-flash'
        
        prompt = """
        Analyze the slide image. Identify the exact bounding box of the square placeholder area (which is a solid grey/white square or a fake QR code) in the right card container.
        Return ONLY the normalized bounding box coordinates of this square area in the format: [ymin, xmin, ymax, xmax], where each value is an integer between 0 and 1000.
        For example, if the square is centered in the right card, it might return [350, 720, 650, 920].
        Do NOT include any markdown, backticks, JSON keys, or explanations. Output ONLY the list of 4 integers, like: [ymin, xmin, ymax, xmax].
        """
        
        print(f"👁️ [Overlay] Querying Gemini Vision ({model_name}) to detect placeholder coordinates...", flush=True)
        response = client.models.generate_content(
            model=model_name,
            contents=[image_part, prompt]
        )
        
        text = response.text.strip()
        print(f"👁️ [Overlay] Gemini Vision response: {text}", flush=True)
        
        # Extract the coordinates using regex
        match = re.search(r'\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]', text)
        if match:
            ymin, xmin, ymax, xmax = map(int, match.groups())
            
            # Convert normalized 0-1000 coordinates to actual slide pixels (e.g. 1920x1080)
            left = int(xmin * slide_w / 1000.0)
            right = int(xmax * slide_w / 1000.0)
            top = int(ymin * slide_h / 1000.0)
            bottom = int(ymax * slide_h / 1000.0)
            
            w = right - left
            h = bottom - top
            
            # Sanity check: must be a reasonable size and proportion
            if w > 50 and h > 50:
                return left, top, w, h
                
        print("⚠️ [Overlay] Gemini Vision returned invalid coordinates or format.", flush=True)
    except Exception as e:
        print(f"❌ [Overlay] Gemini Vision detection failed: {e}", flush=True)
    return None


def apply_overlay_to_slide(session_path: str, slide_number: int, slide_path: str, output_image_path: str):
    """Mathematically aligns and overlays a locally-generated QR code onto the slide image.
    Only supports URL-based QR codes. Custom image overlays are strictly prohibited."""
    from PIL import Image, ImageDraw
    import qrcode
    
    print(f"🔍 [Overlay] Initiating overlay check for Slide {slide_number}...", flush=True)
    metadata = parse_slide_frontmatter(slide_path)
    
    qr_overlay = metadata.get('qr_overlay')
    if not qr_overlay:
        print(f"ℹ️ [Overlay] No qr_overlay parameter found in frontmatter for Slide {slide_number}. Skipping.", flush=True)
        return
        
    print(f"🎯 [Overlay] Found qr_overlay target URL: {qr_overlay}", flush=True)
    is_qr_slide = metadata.get('slide_type') == 'Content (QR Code)'
    
    is_url = qr_overlay.startswith('http://') or qr_overlay.startswith('https://') or qr_overlay.startswith('www.')
    if not is_url:
        print(f"⚠️ [Overlay] qr_overlay '{qr_overlay}' is not a valid URL. Custom image uploads are prohibited.", flush=True)
        return
        
    # Generate the QR Code locally from the URL
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=1,
        )
        qr.add_data(qr_overlay)
        qr.make(fit=True)
        overlay_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        print("✅ [Overlay] Successfully generated QR code locally from URL.", flush=True)
    except Exception as e:
        print(f"❌ [Overlay] Failed to generate QR code for URL {qr_overlay}: {e}", flush=True)
        return
        
    try:
        slide_img = Image.open(output_image_path).convert("RGBA")
        slide_w, slide_h = slide_img.size
        print(f"📊 [Overlay] Widescreen slide base resolution: {slide_w}x{slide_h}", flush=True)
        
        # Proportional scale factor based on standard design width of 1920
        scale_factor = slide_w / 1920.0
        
        # Default target size is 340px (the golden ratio size for the card placeholder)
        try:
            target_size = int(metadata.get('image_size', 340))
        except ValueError:
            target_size = 340
            
        # Scale QR code size proportionally to slide resolution
        actual_target_size = int(target_size * scale_factor)
        
        orig_w, orig_h = overlay_img.size
        aspect_ratio = orig_h / orig_w
        new_w = actual_target_size
        new_h = int(new_w * aspect_ratio)
        overlay_img = overlay_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        position = metadata.get('image_position', 'bottom-right').lower()
        
        if is_qr_slide:
            # Attempt AI-driven dynamic detection using Gemini Multimodal Vision!
            detection = detect_placeholder_with_gemini(output_image_path, slide_w, slide_h)
            detector_success = False
            
            if detection:
                left, top, box_w, box_h = detection
                center_x = left + box_w // 2
                center_y = top + box_h // 2
                print(f"🎯 [Overlay] Gemini Vision SUCCESS! Detected placeholder: left={left}, top={top}, w={box_w}, h={box_h}, center=({center_x}, {center_y})", flush=True)
                
                # Dynamically resize the QR code to perfectly cover the detected placeholder square!
                # We scale it slightly larger (2%) to guarantee a clean cover with no edges peeking out.
                new_w = int(box_w * 1.02)
                new_h = int(box_h * 1.02)
                overlay_img = overlay_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                paste_x = center_x - new_w // 2
                paste_y = center_y - new_h // 2
                detector_success = True
                
            if not detector_success:
                print("⚠️ [Overlay] Gemini Vision detection failed. Falling back to mathematical alignment.", flush=True)
                center_x = int(slide_w * 0.815)
                center_y = int(slide_h * 0.46)
                paste_x = center_x - new_w // 2
                paste_y = center_y - new_h // 2
        else:
            # Fallback bottom-right overlay (for normal slides, draw a white card)
            padding = int(15 * scale_factor)
            card_w = new_w + 2 * padding
            card_h = new_h + 2 * padding
            margin = int(80 * scale_factor)
            
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
                
            draw = ImageDraw.Draw(slide_img)
            card_coords = [card_x, card_y, card_x + card_w, card_y + card_h]
            draw.rounded_rectangle(card_coords, radius=int(12 * scale_factor), fill=(255, 255, 255, 255))
            draw.rounded_rectangle(card_coords, radius=int(12 * scale_factor), outline=(220, 220, 220, 255), width=1)
            
            paste_x = card_x + padding
            paste_y = card_y + padding
            
        # Erase-and-Paste: Draw a solid white square to completely obliterate any background fake QR code!
        draw = ImageDraw.Draw(slide_img)
        # Use a generous margin for QR slides to cover any messy model-generated fake QR blocks
        erase_margin = int(24 * scale_factor) if is_qr_slide else 2
        draw.rectangle([
            paste_x - erase_margin,
            paste_y - erase_margin,
            paste_x + new_w + erase_margin,
            paste_y + new_h + erase_margin
        ], fill=(255, 255, 255, 255))
        
        # Paste the QR code (generated QR code is black/white RGBA, so paste directly is 100% safe)
        slide_img.paste(overlay_img, (paste_x, paste_y))
        
        slide_img.convert("RGB").save(output_image_path, "PNG")
        print(f"💾 [Overlay] Successfully saved final composite image to: {output_image_path}", flush=True)
    except Exception as e:
        print(f"❌ [Overlay] Error applying overlay to slide {slide_number}: {e}", flush=True)


async def generate_slide_image(
    session_path: str,
    slide_number: int,
    tool_context: ToolContext
) -> str:
    """Reads design.md and slide_xx.md from the active session, merges them into a visual prompt,
    and generates the slide image using either Gemini or Vertex AI Imagen."""
    pad_num = f"{slide_number:02d}"
    design_path = os.path.join(session_path, 'design.md')
    slide_path = os.path.join(session_path, f"slide_{pad_num}.md")
    file_path = os.path.join(session_path, 'slides', f"slide_{pad_num}.png")

    if not os.path.exists(design_path):
        return f"Error: Missing design specification: {design_path}."
    if not os.path.exists(slide_path):
        return f"Error: Missing slide content file: {slide_path}."

    try:
        with open(design_path, 'r', encoding='utf-8') as f:
            design_content = f.read()
        with open(slide_path, 'r', encoding='utf-8') as f:
            slide_content = f.read()
    except Exception as e:
        return f"Failed to read specification files: {str(e)}"

    prompt = f"""Generate a professional 16:9 widescreen (1920×1080 px) presentation slide image based on the brand system and the slide specifications below.
You MUST output exactly one image.

<brand_system>
{design_content}
</brand_system>

<slide_spec>
{slide_content}
</slide_spec>
"""

    client = genai.Client()
    is_gemini_image_model = CONFIG['IMAGEN_MODEL'].startswith('gemini-')

    try:
        if is_gemini_image_model:
            response = await _call_with_retry(
                lambda: client.aio.models.generate_content(
                    model=CONFIG['IMAGEN_MODEL'],
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        modality_settings={
                            "image": {
                                "image_settings": {
                                    "aspect_ratio": "16:9",
                                    "image_size": "2K"
                                }
                            }
                        }
                    )
                )
            )
            raw_data = None
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                        raw_data = part.inline_data.data
                        break
            if not raw_data:
                return "Failed to generate slide: No image bytes returned in Gemini response."
            image_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data
        else:
            result = await _call_with_retry(
                lambda: client.aio.models.generate_images(
                    model=CONFIG['IMAGEN_MODEL'],
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/png",
                        aspect_ratio="16:9",
                    )
                )
            )
            if not result.generated_images:
                return "Failed to generate slide: No images returned by Imagen API."
            image_bytes = result.generated_images[0].image.image_bytes

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(image_bytes)

        # Apply overlay (if any) to the file on disk (synchronously)
        apply_overlay_to_slide(session_path, slide_number, slide_path, file_path)

        # Read the (possibly modified) file back to get the final image bytes
        with open(file_path, 'rb') as f:
            image_bytes = f.read()

        # Save as artifact and record the GCS version in session state
        artifact_part = Part.from_bytes(data=image_bytes, mime_type="image/png") if 'Part' in globals() else types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        version = await save_artifact_helper(f"slide_{pad_num}.png", artifact_part, tool_context)
        tool_context.state[f"slide_{pad_num}_gcs_version"] = version

        # Global persistent GCS store (critical for cloud container restarts and distributed instances)
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
    Only supported by native multimodal Gemini models (not traditional Imagen)."""
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
...
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
        return "Error: generate_sequence_images requires a native Gemini multimodal model. Traditional Imagen models cannot generate multiple images per prompt."

    try:
        response = await _call_with_retry(
            lambda: client.aio.models.generate_content(
                model=CONFIG['IMAGEN_MODEL'],
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    modality_settings={
                        "image": {
                            "image_settings": {
                                "aspect_ratio": "16:9",
                                "image_size": "2K"
                            }
                        }
                    }
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
        
        warning = ""
        if len(image_parts) != len(slide_numbers):
            warning = f"Warning: Requested {len(slide_numbers)} images but model returned {len(image_parts)}. "

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
                
            # Apply overlay (if any) to the file on disk (synchronously)
            slide_path = os.path.join(session_path, f"slide_{pad_num}.md")
            apply_overlay_to_slide(session_path, slide_number, slide_path, file_path)
            
            # Read the (possibly modified) file back to get the final image bytes
            with open(file_path, 'rb') as f:
                image_bytes = f.read()

            artifact_part = Part.from_bytes(data=image_bytes, mime_type="image/png") if 'Part' in globals() else types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            version = await save_artifact_helper(f"slide_{pad_num}.png", artifact_part, tool_context)
            tool_context.state[f"slide_{pad_num}_gcs_version"] = version

            gcs_versions[f"slide_{pad_num}_gcs_version"] = version
            results.append(f"slide_{pad_num}.png saved")

        write_gcs_versions(session_id, gcs_versions)
        return warning + "Successfully generated and saved sequence images: " + ", ".join(results)

    except Exception as e:
        return f"Failed to generate sequence images: {str(e)}"
