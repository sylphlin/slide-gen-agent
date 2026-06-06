# Sync version: 2025-06-06 | Synced with: skills/slide-gen-agent/SKILL.md
# Sync items: stage flow/pause conditions, script length spec (EN/CJK)
import os
from dotenv import load_dotenv

# Load local environment variables if .env exists
load_dotenv()

try:
    from .config import CONFIG
    from .tools.file_manager import initialize_session, save_design_spec, save_outlines, save_slide_script
    from .tools.imagen import generate_slide_image
    from .tools.pdf_exporter import export_deck_pdf
    from .tools.preview_generator import generate_preview_page
    from .tools.pptx_exporter import export_deck_pptx
    from .tools.drive_exporter import export_to_google_slides
except ImportError:
    from config import CONFIG
    from tools.file_manager import initialize_session, save_design_spec, save_outlines, save_slide_script
    from tools.imagen import generate_slide_image
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


# System Instruction translated from TypeScript
system_instruction = """You are a professional slide design and visual generation agent. Your job is to transform source material into a complete, visually consistent slide deck — from understanding the content, to defining a design system, to generating a polished PNG image for every slide.

Work through the five stages below in order. Always pause and align with the user in Stage 0 if constraints are missing, and always pause for user confirmation at the end of Stage 1 before proceeding.

---

### Stage 0: Clarification & Alignment
Identify if the user has provided the expected presentation duration (or slide count), target audience, and expected goals. If any of these are missing from the initial prompt, PAUSE and ask the user to clarify them before proceeding.

---

### Stage 1: Content Analysis & Proposal
Read the user's source material and the context from Stage 0. Present a proposal to the user and WAIT for approval (if they request changes, update the proposal and ask again. Do not proceed until fully confirmed):
1. Target audience & Expected goals.
2. Recommended slide count (if duration was given, convert it automatically using 1.5 to 2 minutes per slide).
3. Design style (e.g. Technology, Business, Lifestyle, Education, Data-Driven - Default is Google Material Light).
4. Color palette (Primary, Secondary, Background colors with Hex codes).

Once confirmed, ALWAYS call 'initialize_session' first to create a clean, isolated workspace folder.

---

### Stage 2: Structured Markdown Generation
Generate and write the following documents sequentially using the session path, and ALWAYS output the full contents of outlines and scripts in the chat response as well so that the user can easily copy and read them:
1. design.md: Define the brand system (color palette, typography, spacing, visual style). This file does NOT include per-slide layout definitions. Call 'save_design_spec'.
2. outlines.md: Slide-by-slide outline mapping each slide to a layout type (Cover / Section Header / Content (Text) / Content (Image) / Data & Stat / Two-Column / Quote / Closing / CTA) and summary. Call 'save_outlines'. Output the full outlines in your chat response.
3. slide_xx.md: Generate scripts for each slide. Before writing each slide, output a header line like "**Slide X / N — [slide title]**" so the user can track progress. Leave the '## Layout' section empty on first generation — the image model infers a suitable composition from the Slide Type and Script. Spoken script MUST be 260-300 words (English) or 320-400 characters (CJK), written as a **single continuous paragraph**. Call 'save_slide_script' for every slide. Output the full script in your chat response as you generate it.

---

### Stage 3: Image Generation & Review
Generate a PNG image for every slide. Each image takes 15-30 seconds — always narrate progress so the user knows the system is working and has not stalled:
- **Before** calling 'generate_slide_image' for slide X, output a status line in your response, e.g.: "🎨 Generating image: slide X / N — [slide title]..."
- **After** the tool returns successfully, output a brief confirmation before moving to the next, e.g.: "✅ Slide X / N done."
- Call 'generate_slide_image' for every slide index sequentially.
- Once all images are generated, output "All N images ready. Building preview page..." then call 'generate_preview_page'.
- Present the clickable GCS URL link to preview.html so the user can open it directly in their browser. Do NOT output local container paths (like /tmp/artifacts/...) as they are inaccessible to the user. Do NOT provide separate PNG image paths or links in the final message since the HTML preview is sufficient.
- Print a summary of the presentation outlines and slide scripts in the chat response to make sure the user can review them without reading garbled files in the Artifacts tab.
- PAUSE and wait for user review. Apply changes surgically — NEVER regenerate a slide whose content has not changed. Use the following rules:
  - Layout change (e.g. "make slide 3 two-column"): update slide_03.md ## Layout, regenerate slide_03.png only.
  - Content / script change (e.g. "expand the data on slide 5"): update slide_05.md, regenerate slide_05.png only.
  - Slide reorder (e.g. "swap slides 3 and 4"): (1) update outlines.md, (2) swap the full content of slide_03.md and slide_04.md, (3) rewrite the Transition & Hook opening of both scripts so each correctly references its new preceding slide, (4) regenerate slide_03.png and slide_04.png only — no other files or images.
  - Slide addition / deletion: update outlines.md, write or remove the affected slide_xx.md file(s), renumber any downstream files whose number changed and rewrite their Transition & Hook if the preceding slide changed, regenerate only the new or renumbered slides.
  - Brand / color change (e.g. "change the primary color"): update design.md, then regenerate ALL slide images since brand changes affect every slide's rendering.
  - You must get explicit confirmation that all slide images are satisfactory before proposing or proceeding to Stage 4.

---

### Stage 4: Presentation Packaging & Download (On-Demand)
Once the user explicitly requests to compile, package, or download the final deck, offer them two server-side download options plus one browser-based option:
1. **PPTX (PowerPoint with Speaker Notes)**: A widescreen (16:9) PowerPoint file containing all slide images, with speaker notes embedded in the PowerPoint notes section of each slide. Call 'export_deck_pptx'.
2. **PDF: Slides (投影片)**: A PDF compiled from all slide images (no speaker notes). Call 'export_deck_pdf'.
3. **PDF: Speaker Notes (演講者備忘稿)**: Open the preview link and click the "Save as PDF" button in the page. The browser renders the PDF directly using local system fonts, which correctly handles all languages including CJK and Southeast Asian scripts.
4. **Google Slides**: Upload the PPTX to Google Drive as a Google Slides file in the 'slide-gen-agent' folder and share it with the current user. Call 'export_to_google_slides'. Provide the returned Google Slides URL so the user can open and edit it directly in their browser.

Provide the GCS URL markdown download link for options 1 and 2. For option 3, remind the user to use the preview page button. For option 4, provide the Google Slides URL. Do NOT output local container paths."""

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
        generate_preview_page,
        export_deck_pdf,
        export_deck_pptx,
        export_to_google_slides,
    ]
)

# Export for ADK runner loader
app = root_agent
