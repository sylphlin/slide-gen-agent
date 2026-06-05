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
except ImportError:
    from config import CONFIG
    from tools.file_manager import initialize_session, save_design_spec, save_outlines, save_slide_script
    from tools.imagen import generate_slide_image
    from tools.pdf_exporter import export_deck_pdf
    from tools.preview_generator import generate_preview_page

from google.adk import Agent
from google.genai import types

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
Generate and write the following documents sequentially using the session path:
1. design.md: Define the visual system. Call 'save_design_spec'.
2. outlines.md: Design outline mapping each slide to a layout type and summary. Call 'save_outlines'.
3. slide_xx.md: Generate scripts for each slide. Spoken script MUST be 260-300 words (English) or 320-400 characters (Chinese), structured with a transition and deep dive, and evocative. Call 'save_slide_script' for every slide.

---

### Stage 3: Image Generation & Review
Generate a PNG image for every slide:
- Call 'generate_slide_image' for every slide index.
- Once all slide images are generated, call 'generate_preview_page' to create a preview.html file.
- Present the path/link to preview.html and display slide images.
- PAUSE and wait for user review. If changes are requested, regenerate the corresponding markdown files and images. You must get explicit confirmation that all slide images are satisfactory before proposing or proceeding to Stage 4.

---

### Stage 4: Widescreen PDF Packaging (On-Demand)
Once the user explicitly requests to compile, package, or download the final deck:
- Call 'export_deck_pdf' to compile the PNGs into a single PDF.
- Provide the markdown download link to the compiled PDF file."""

# Default Text Model selection
text_model = CONFIG['TEXT_MODEL']

# Determine if model requires thinking configuration
is_thinking_model = "-thinking" in text_model or "3.5-flash" in text_model or "3.5-pro" in text_model

generate_content_config = None
if is_thinking_model:
    # Set thinking config based on CONFIG
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=CONFIG['THINKING_LEVEL'].upper() if CONFIG['THINKING_LEVEL'] else None,
            thinking_budget=CONFIG['THINKING_BUDGET'] if not CONFIG['THINKING_LEVEL'] else None
        )
    )

# Instantiate the Python ADK 2.0 Agent
root_agent = Agent(
    name="slide_gen_agent",
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
    ]
)

# Export for ADK runner loader
app = root_agent
