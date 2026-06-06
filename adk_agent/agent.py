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
    from .tools.notes_pdf_exporter import export_speaker_notes_pdf
except ImportError:
    from config import CONFIG
    from tools.file_manager import initialize_session, save_design_spec, save_outlines, save_slide_script
    from tools.imagen import generate_slide_image
    from tools.pdf_exporter import export_deck_pdf
    from tools.preview_generator import generate_preview_page
    from tools.pptx_exporter import export_deck_pptx
    from tools.notes_pdf_exporter import export_speaker_notes_pdf

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
1. design.md: Define the visual system. Call 'save_design_spec'.
2. outlines.md: Design outline mapping each slide to a layout type and summary. Call 'save_outlines'. Output the full outlines in your chat response.
3. slide_xx.md: Generate scripts for each slide. Before writing each slide, output a header line like "**Slide X / N — [slide title]**" so the user can track progress. Spoken script MUST be 260-300 words (English) or 320-400 characters (CJK), written as a **single continuous paragraph** (do NOT split into multiple paragraphs, but still maintain smooth transitions, professional tone, and evocative delivery). Call 'save_slide_script' for every slide. Output the full script in your chat response as you generate it.

---

### Stage 3: Image Generation & Review
Generate a PNG image for every slide. Each image takes 15-30 seconds — always narrate progress so the user knows the system is working and has not stalled:
- **Before** calling 'generate_slide_image' for slide X, output a status line in your response, e.g.: "🎨 Generating image: slide X / N — [slide title]..."
- **After** the tool returns successfully, output a brief confirmation before moving to the next, e.g.: "✅ Slide X / N done."
- Call 'generate_slide_image' for every slide index sequentially.
- Once all images are generated, output "All N images ready. Building preview page..." then call 'generate_preview_page'.
- Present the clickable GCS URL link to preview.html so the user can open it directly in their browser. Do NOT output local container paths (like /tmp/artifacts/...) as they are inaccessible to the user. Do NOT provide separate PNG image paths or links in the final message since the HTML preview is sufficient.
- Print a summary of the presentation outlines and slide scripts in the chat response to make sure the user can review them without reading garbled files in the Artifacts tab.
- PAUSE and wait for user review. If changes are requested, regenerate the corresponding markdown files and images. You must get explicit confirmation that all slide images are satisfactory before proposing or proceeding to Stage 4.

---

### Stage 4: Presentation Packaging & Download (On-Demand)
Once the user explicitly requests to compile, package, or download the final deck, offer them three distinct download options:
1. **PPTX (PowerPoint with Speaker Notes)**: A widescreen (16:9) PowerPoint file containing all slide images, with speaker notes embedded in the PowerPoint notes section of each slide. Call 'export_deck_pptx'.
2. **PDF: Slides (投影片)**: A PDF compiled from all slide images (no speaker notes). Call 'export_deck_pdf'.
3. **PDF: Speaker Notes (演講者備忘稿)**: A PDF showing each slide's image followed by its title and speaker notes (matching the preview.html layout). Call 'export_speaker_notes_pdf'.

Provide the GCS URL markdown download link for the compiled file(s) that the user requests. Do NOT output local container paths."""

# Default Text Model selection
text_model = CONFIG['TEXT_MODEL']

# Determine if model requires thinking configuration
is_thinking_model = "-thinking" in text_model or "3.5-flash" in text_model or "3.5-pro" in text_model

generate_content_config = None
if is_thinking_model:
    _budget = CONFIG['THINKING_BUDGET']
    if _budget is not None:
        _thinking_config = types.ThinkingConfig(thinking_budget=_budget)
    else:
        _thinking_config = types.ThinkingConfig(
            thinking_level=getattr(types.ThinkingLevel, CONFIG['THINKING_LEVEL'].upper(), types.ThinkingLevel.HIGH)
        )
    generate_content_config = types.GenerateContentConfig(thinking_config=_thinking_config)

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
        export_speaker_notes_pdf,
    ]
)

# Export for ADK runner loader
app = root_agent
