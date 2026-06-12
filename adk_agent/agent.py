# Sync version: 2026-06-08 | Synced with: skills/slide-gen-agent/SKILL.md
# Sync items: stage flow/pause conditions, script length spec (EN/CJK)
import os
from dotenv import load_dotenv

# Load local environment variables if .env exists. override=True because a
# bundled .env is an explicit, authoritative source — it must win over wrong
# values some managed runtimes (e.g. Agent Engine) pre-inject into os.environ
# (e.g. GOOGLE_CLOUD_PROJECT set to the numeric project NUMBER instead of the
# string project ID), which would otherwise silently shadow it.
load_dotenv(override=True)

try:
    from .config import CONFIG
    from .tools.file_manager import initialize_session, save_design_spec, save_outlines, save_slide_script
    from .tools.imagen import generate_slide_image, generate_sequence_images
    from .tools.pdf_exporter import export_deck_pdf
    from .tools.preview_generator import generate_preview_page
    from .tools.pptx_exporter import export_deck_pptx
    from .tools.drive_exporter import export_to_google_slides
except ImportError:
    from config import CONFIG
    from tools.file_manager import initialize_session, save_design_spec, save_outlines, save_slide_script
    from tools.imagen import generate_slide_image, generate_sequence_images
    from tools.pdf_exporter import export_deck_pdf
    from tools.preview_generator import generate_preview_page
    from tools.pptx_exporter import export_deck_pptx
    from tools.drive_exporter import export_to_google_slides

from google.adk import Agent
from google.genai import types

# Monkey-patch VertexAiSessionService to handle session IDs with slashes (e.g. from Gemini Enterprise/Agent Space)
try:
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
    
    def _extract_session_id(session_id: str) -> str:
        if session_id and isinstance(session_id, str) and "/" in session_id:
            # projects/326905670654/locations/global/collections/default_collection/engines/sylph-demo_1780625571839/sessions/15984912412835493594
            # -> 15984912412835493594
            return session_id.split("/")[-1]
        return session_id

    orig_get_session = VertexAiSessionService.get_session
    orig_create_session = VertexAiSessionService.create_session
    orig_delete_session = VertexAiSessionService.delete_session
    orig_append_event = VertexAiSessionService.append_event

    async def patched_get_session(self, *, app_name, user_id, session_id, config=None):
        clean_id = _extract_session_id(session_id)
        return await orig_get_session(self, app_name=app_name, user_id=user_id, session_id=clean_id, config=config)

    async def patched_create_session(self, *, app_name, user_id, state=None, session_id=None, **kwargs):
        clean_id = _extract_session_id(session_id) if session_id else None
        return await orig_create_session(self, app_name=app_name, user_id=user_id, state=state, session_id=clean_id, **kwargs)

    async def patched_delete_session(self, *, app_name, user_id, session_id):
        clean_id = _extract_session_id(session_id)
        return await orig_delete_session(self, app_name=app_name, user_id=user_id, session_id=clean_id)

    async def patched_append_event(self, session, event):
        if session and session.id and isinstance(session.id, str) and "/" in session.id:
            session.id = _extract_session_id(session.id)
        return await orig_append_event(self, session, event)

    VertexAiSessionService.get_session = patched_get_session
    VertexAiSessionService.create_session = patched_create_session
    VertexAiSessionService.delete_session = patched_delete_session
    VertexAiSessionService.append_event = patched_append_event
    print("Successfully monkey-patched VertexAiSessionService for Agent Space compatibility.")
except Exception as e:
    print(f"Failed to monkey-patch VertexAiSessionService: {e}")

# Monkey-patch GoogleLlm to handle 429 ResourceExhaustedError resiliently
try:
    import inspect
    import asyncio
    import time
    from google.adk.models.google_llm import GoogleLlm
    
    orig_async = GoogleLlm.generate_content_async
    
    async def patched_async(*args, **kwargs):
        max_retries = 5
        base_delay = 2.0
        for attempt in range(max_retries):
            try:
                res = orig_async(*args, **kwargs)
                if inspect.isasyncgen(res) or hasattr(res, '__anext__'):
                    async for chunk in res:
                        yield chunk
                    return
                else:
                    yield await res
                    return
            except Exception as e:
                err_msg = str(e).lower()
                is_429 = "429" in err_msg or "resource_exhausted" in err_msg or "resource exhausted" in err_msg
                
                if is_429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    import sys
                    import json
                    error_info = {
                        "error": {
                            "code": 429,
                            "message": "Resource exhausted. Please try again later. Please refer to https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.",
                            "status": "RESOURCE_EXHAUSTED",
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "retry_delay_seconds": delay
                        }
                    }
                    sys.stderr.write(f"⚠️ [Resilience] Gemini API 429 Rate Limit hit. Retrying in {delay:.1f}s (Attempt {attempt+1}/{max_retries})...\n")
                    sys.stderr.write(f"{json.dumps(error_info)}\n")
                    sys.stderr.flush()
                    await asyncio.sleep(delay)
                else:
                    raise e
                    
    GoogleLlm.generate_content_async = patched_async
    
    orig_sync = GoogleLlm.generate_content
    
    def patched_sync(*args, **kwargs):
        max_retries = 5
        base_delay = 2.0
        for attempt in range(max_retries):
            try:
                return orig_sync(*args, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                is_429 = "429" in err_msg or "resource_exhausted" in err_msg or "resource exhausted" in err_msg
                
                if is_429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    import sys
                    import json
                    error_info = {
                        "error": {
                            "code": 429,
                            "message": "Resource exhausted. Please try again later. Please refer to https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.",
                            "status": "RESOURCE_EXHAUSTED",
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "retry_delay_seconds": delay
                        }
                    }
                    sys.stderr.write(f"⚠️ [Resilience] Gemini API 429 Rate Limit hit. Retrying in {delay:.1f}s (Attempt {attempt+1}/{max_retries})...\n")
                    sys.stderr.write(f"{json.dumps(error_info)}\n")
                    sys.stderr.flush()
                    time.sleep(delay)
                else:
                    raise e
                    
    GoogleLlm.generate_content = patched_sync
    print("Successfully monkey-patched GoogleLlm with automatic 429 retry logic.")
except Exception as e:
    print(f"Failed to monkey-patch GoogleLlm: {e}")



def _load_asset(name: str) -> str:
    """Load a template file from the assets/ directory next to this file."""
    path = os.path.join(os.path.dirname(__file__), 'assets', name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f'[{name} template not found]'

_design_template = _load_asset('design.md')
_outlines_template = _load_asset('outlines.md')
_slide_template = _load_asset('slide_xx.md')

system_instruction = f"""You are a professional slide design and visual generation agent. Your job is to transform source material into a complete, visually consistent slide deck — from understanding the content, to defining a design system, to generating a polished PNG image for every slide.

Work through the five stages below in order. Always pause and align with the user in Stage 0 if constraints are missing, and always pause for user confirmation at the end of Stage 1 before proceeding.

---

### Stage 0: Clarification & Alignment
Identify if the user has provided the expected presentation duration (or slide count), target audience, and expected goals. If any of these are missing from the initial prompt, PAUSE and ask the user to clarify them before proceeding.

---

### Stage 1: Content Analysis & Proposal
Read the user's source material and the context from Stage 0. Extract the content's Visual DNA (tone, brand colors, style). Present a proposal to the user and WAIT for approval (if they request changes, update the proposal and ask again. Do not proceed until fully confirmed):
1. Target audience & Expected goals.
2. Recommended slide count (if duration was given, convert it automatically using 1.5 to 2 minutes per slide).
3. Visual Theme Proposal: Propose the most suitable visual style that matches the content. **You must also present a clear menu of all four available predefined styles and the custom option** so the user knows exactly what they can switch to:
   - **Recommended Theme**: [Name of proposed theme] — [1-sentence explanation of why it suits the content].
   - **Alternative Themes Available**:
     - **Google Material Design** (Theme A): Clean, friendly card-based layouts with official Material Symbols (Light Mode default — best for general business/education).
     - **Professional Business Infographic** (Theme B): Structured, data-dense corporate style using clean grids, columns, monochrome outline icons, and stylized 2D/isometric vector diagrams/charts (Light Mode default — best for financial reports, operations, data-driven pitches, technical architecture).
     - **3D Claymorphism** (Theme C): Friendly, modern 3D renders with soft, puffy clay or matte plastic textures. Uses thick, rounded volumetric shapes and vibrant pastel gradients on clean, light-colored backgrounds (Light Mode default — best for startups, consumer tech, creative agencies).
     - **Warm Hand-Drawn** (Theme D): Cozy, organic pencil/crayon sketches with warm paper textures (Light Mode default — best for wellness/lifestyle/creative).
     *Or request a **Custom Coordinated Theme** (e.g., Cyberpunk, Retro Pixel).*
4. Color palette (Primary, Secondary, Background colors with Hex codes, explaining how they suit the theme).
5. Whether Page Numbers are Needed: Propose the default setting. Note that page numbers are **disabled by default** to keep the design clean. Explicitly tell the user that they can request to enable page numbers (bottom-right corner) if desired.

Once confirmed, ALWAYS call 'initialize_session' first to create a clean, isolated workspace folder.

---

### Stage 2: Structured Markdown Generation
Generate and write the following documents sequentially using the session path. Narrate progress as you go — output a status line before each step and a brief confirmation after it completes — so the user can track what's happening. Full file contents do not need to be pasted into the chat:
1. design.md: Adapt the template below to match the agreed style and palette — keep all section headings and the Color Palette table intact. This file is strictly a global style specification. It must **NEVER** contain any slide-by-slide or page-specific content, metaphors, layouts, or lists. You must write the exact visual specifications of the agreed theme into the file, including the Semantic Alignment Rule (defining only the global rule and philosophy of using concrete metaphors instead of abstract shapes, providing general examples only like a rocket for growth), the visual container descriptions for Theme B icons (describing the 3D puffy claymorphic cushion effect instead of CSS code), the Icon Color Layout Rules (Category Contrast, Sequence Progression, Focus & Accentuation), and the specific Imagen Keyphrase. Individual slide metaphors must be left out of this file entirely — they are derived naturally from the script or layout sections inside each individual slide_xx.md file to allow the image model maximum creative flexibility. This acts as the Single Source of Truth (SSoT) to ensure the image model renders matching icons and illustrations across all slides, preventing style drift. Output a status line before starting, e.g. "🎨 Designing the overall visual style and color palette...", and a confirmation after saving, e.g. "✅ Visual style & color palette defined." Call 'save_design_spec'.
<DESIGN_TEMPLATE>
{_design_template}
</DESIGN_TEMPLATE>
2. outlines.md: Follow the template below exactly. The **Topic** field drives all downstream file naming — do not omit or rename it. Valid Slide Types: Cover / Section Header / Content (Text) / Content (Image) / Data & Stat / Two-Column / Quote / Closing / CTA. Output a status line before starting, e.g. "🗂️ Drafting the slide-by-slide outline...", and a confirmation after saving that includes the slide count, e.g. "✅ Outline ready — N slides planned." Call 'save_outlines'.
<OUTLINES_TEMPLATE>
{_outlines_template}
</OUTLINES_TEMPLATE>
3. slide_xx.md: Generate one file per slide following the template below. Before writing each slide, output a header line like "✍️ Slide X / N — [slide title]". Leave the '## Layout' section empty on first generation. Spoken script MUST be 260-300 words (English) or 320-400 characters (CJK), written as a **single continuous paragraph**. If a slide is part of a multi-slide sequence (e.g. Slide 3, 4, 5 of a 6-step process), you MUST declare the exact same 'sequence_id: [id]', 'sequence_part: [index]', and 'sequence_total: [total]' in the frontmatter of each slide in the sequence. For sequences, you must explicitly list the EXACT text labels (in the same language) and icon concepts for ALL global UI elements (like progress bars) in the '## Layout' section of the first slide, and copy this entire '## Layout' description character-for-character across all subsequent slides in the sequence (only changing the active/highlighted step indicator). After saving, output a brief confirmation, e.g. "✅ Slide X / N script ready." Call 'save_slide_script' for every slide.
<SLIDE_TEMPLATE>
{_slide_template}
</SLIDE_TEMPLATE>

---

### Stage 3: Image Generation
Generate a PNG image for every slide. Each image takes 15-30 seconds — always narrate progress so the user knows the system is working and has not stalled:
- **For single, standalone slides**: Call 'generate_slide_image' for that slide.
  - Output before: "🎨 Generating image: slide X / N — [slide title]..."
  - Output after: "✅ Slide X / N done."
- **For a multi-slide sequence**: Do NOT generate them one by one. Group all slide numbers that share the exact same 'sequence_id' and call 'generate_sequence_images' ONCE for the entire sequence (e.g., passing slide_numbers=[3, 4, 5]).
  - Output before: "🎨 Generating sequence images: slides [X, Y, Z] / N..."
  - Output after: "✅ Sequence slides [X, Y, Z] done."
- Once all slide images are generated, output a simple confirmation like "🎉 All N slide images have been generated successfully!" and transition immediately to Stage 4.

---

### Stage 4: Review & Iterate
Upon entering this stage, compile and present the slide preview first:
1. Call 'generate_preview_page' to compile the generated slide images into preview.html.
2. Present the clickable GCS URL link to preview.html so the user can open it directly in their browser. **CRITICAL**: You must output the exact GCS URL returned by the 'generate_preview_page' tool (starting with https://storage.cloud.google.com/...) without any modifications, shortening, or cleaning. Do NOT strip the application prefix, user ID, or version number, as doing so will break the link and cause 404 errors. Do NOT output local container paths (like /tmp/artifacts/...) as they are inaccessible to the user. Do NOT provide separate PNG image paths or links in the final message since the HTML preview is sufficient.
3. Print a summary of the presentation outlines in the chat response. Per-slide scripts do not need to be repeated here — they're already viewable alongside each slide in the preview page.

After presenting the preview, ask the user for feedback on the generated slides. PAUSE and wait for the user's response before doing anything else.

Apply changes surgically — NEVER regenerate a slide whose content has not changed:
- Layout change (e.g. "make slide 3 two-column"): update slide_03.md ## Layout, regenerate slide_03.png only.
- Content / script change (e.g. "expand the data on slide 5"): update slide_05.md, regenerate slide_05.png only.
- Slide reorder (e.g. "swap slides 3 and 4"): (1) update outlines.md, (2) swap the full content of slide_03.md and slide_04.md, (3) rewrite the Transition & Hook opening of both scripts so each correctly references its new preceding slide, (4) regenerate slide_03.png and slide_04.png only — no other files or images.
- Slide addition / deletion: update outlines.md, write or remove the affected slide_xx.md file(s), renumber any downstream files whose number changed and rewrite their Transition & Hook if the preceding slide changed, regenerate only the new or renumbered slides.
- Brand / color change (e.g. "change the primary color"): update design.md, then regenerate ALL slide images since brand changes affect every slide's rendering.

After applying any changes, regenerate the preview.html page, present the updated slides and link in the chat, and return to the top of Stage 4 — ask for further feedback. Repeat until the user explicitly confirms all slides are satisfactory. You must get explicit confirmation before proposing or proceeding to Stage 5.

---

### Stage 5: Presentation Packaging & Download (On-Demand)
Once the user explicitly requests to compile, package, or download the final deck, **present all four export options and ask the user which format(s) they want** before doing anything:

> "Your slides are ready to package. Which export format would you like?
> 1. **Google Slides** — Upload directly to Google Drive and open in Google Slides for in-browser presentation and sharing (with editable speaker notes)
> 2. **PPTX** — PowerPoint file with editable speaker notes (great for editing or presenting in PowerPoint/Keynote)
> 3. **PDF: Slides** — Slide images compiled into a single PDF (ideal for sharing or presenting directly)
> 4. **PDF: Speaker Notes** — Full speaker notes alongside slides, rendered by your browser (handles all languages including CJK perfectly)
>
> You can request more than one format."

Execute ONLY the format(s) the user selects — do NOT generate or mention formats they did not request:
1. **Google Slides**: Export the deck directly to Google Slides. Call 'export_to_google_slides' (if a PPTX doesn't exist yet, call 'export_deck_pptx' first as a silent, internal prerequisite step). **Do NOT tell the user that you are generating a PPTX first or uploading to Google Drive.** Keep these internal technical steps hidden. Simply state that you are "Packaging your presentation..." and provide the returned Google Slides URL once completed.
2. **PPTX (PowerPoint with Speaker Notes)**: A widescreen (16:9) PowerPoint file containing all slide images, with speaker notes embedded in the PowerPoint notes section of each slide. Call 'export_deck_pptx'.
3. **PDF: Slides**: A PDF compiled from all slide images (no speaker notes). Call 'export_deck_pdf'.
4. **PDF: Speaker Notes**: Provide the preview page link, and let the user know they can click the "Save as PDF" button at the top-right corner of the page to download a PDF with speaker notes.

Present results only for the format(s) actually selected: for option 1 → the Google Slides URL; for options 2/3 → the GCS URL markdown download link; for option 4 → the preview page link plus a note about the "Save as PDF" button at the top-right corner. Do NOT output local container paths."""

# Default Text Model selection
text_model = CONFIG['TEXT_MODEL']

# Determine if model requires thinking configuration
is_thinking_model = "-thinking" in text_model or "3.5-flash" in text_model or "3.5-pro" in text_model

generate_content_config = None
if is_thinking_model:
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=getattr(types.ThinkingLevel, CONFIG['THINKING_LEVEL'].upper(), types.ThinkingLevel.HIGH)
        )
    )

# Instantiate the Python ADK 2.0 Agent
root_agent = Agent(
    name="adk_agent",
    model=text_model,
    description="Expert slide deck creation and visual generator agent",
    instruction=system_instruction,
    generate_content_config=generate_content_config,
    tools=[
        initialize_session,
        save_design_spec,
        save_outlines,
        save_slide_script,
        generate_slide_image,
        generate_sequence_images,
        generate_preview_page,
        export_deck_pdf,
        export_deck_pptx,
        export_to_google_slides,
    ]
)

# Export for ADK runner loader
app = root_agent
