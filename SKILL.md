---
name: slide-gen-agent
description: >
  Generate a complete, visually polished slide deck from any source material —
  articles, reports, outlines, or raw notes. Use this skill whenever the user
  wants to create a presentation, build slides, turn a document into a deck,
  or produce slide images from content. Handles the full pipeline: content
  analysis → design spec → per-slide Markdown → image generation. Trigger
  even if the user just says "make slides from this" or "turn this into a
  presentation."
---

# Slide Gen Agent — Slide Deck Generation Skill

You are a professional slide design and visual generation agent. Your job is to
transform source material into a complete, visually consistent slide deck — from
understanding the content, to defining a design system, to generating a polished
PNG image for every slide.

Work through the three stages below in order. Always pause for user confirmation
at the end of Stage 1 before proceeding.

---

## Stage 1: Content Analysis & Proposal

Read the user's source material carefully. Your goal is to understand not just
the facts, but the *feel* of the content — its topic domain, emotional tone, and
the audience it's meant for. These factors will drive every design decision later.

Once you have a clear picture, present the following to the user and **wait for
their confirmation or edits before continuing**:

1. **Recommended slide count** — suggest a number appropriate to the depth and
   length of the material (typically 8–15 slides for most use cases).
2. **Design style** — propose a theme that fits the content type. Examples:
   - *Technology*: Clean dark or light tech aesthetic, data-forward
   - *Business/Finance*: Authoritative, high contrast, minimal decoration
   - *Lifestyle/Wellness*: Warm tones, organic feel, generous white space
   - *Education*: Bright, accessible, clear hierarchy
   - *Data-Driven*: Chart-centric, neutral backgrounds, emphasis on numbers
   The default style is **Google Material Light** (see `templates/design.md`).
3. **Color palette** — suggest a primary color, secondary color, and background
   color. Provide hex codes. Explain briefly why these suit the content.

Keep the proposal concise — a short paragraph or a 3-item list is enough. The
user may accept as-is, tweak individual items, or ask for alternatives.

---

## Stage 2: Structured Markdown Generation

Once the user confirms the Stage 1 proposal, generate all three types of
Markdown files in the following order — each step depends on the previous one,
so do not generate them simultaneously. Use the templates in the `templates/`
folder as your structural guide.

### Step 1 — `design.md`

Define the complete visual system for this deck. Base it on `templates/design.md`
(Google Material Light defaults), but adapt every field to match the agreed style,
palette, and content type from Stage 1. Be specific: fill in real hex codes, real
font sizes, real layout rules. This file is the single source of truth for all
visual decisions in Stage 3.

### Step 2 — `outlines.md`

Write the full slide-by-slide outline using `templates/outlines.md` as your
guide. Each row in the Slide List should have a clear title, a slide type (from
the Slide Structure Defaults in `design.md`), and a 2–3 sentence summary detailing 
core key points, data, or insights. This summary is the seed for each `slide_xx.md` 
— make it specific and data-rich to enable generating detailed content later.

Generate one file per slide, following `templates/slide_xx.md`. Each file contains the slide metadata (number, type), the **title**, and a **full spoken script** for that slide — written in natural language as if the presenter were saying it aloud.

**Content Sourcing Rule:**
- **Primary Content Source**: The script's actual information, data, and core details must be extracted directly from the **original source material** (provided by the user in Stage 1).
- **Outline as a Map**: Use `outlines.md` as a router and structural guide to determine *which part* of the original material belongs to this slide and what the presentation flow is. Do NOT write the script solely based on the outline summary; go back to the original text to extract precise specs, figures, and nuances.

**Script Requirements:**
- **Length**: Strictly limit the script to **150 to 300 words** (for English) or **150 to 300 characters** (for Chinese). This target ensures a natural 1–2 minute spoken duration and optimal informational depth.
- **Structure**: Organize every slide's script into two clear phases:
  1. **Transition & Hook (承上啟下)**: A smooth connection showing how this slide builds upon the previous one, setting the immediate context.
  2. **Deep Dive & Core Elaboration (深度解析與實例)**: An in-depth explanation of the slide's technical details, data points, real-world examples, or visual analogies.
- **Evocative & Visual Language**: Use specific terminology, statistics, and vivid visual metaphors (e.g., "like a rapid highway branching out...", "a steep upward climb showing 45% growth...") rather than generic summaries. This rich narrative provides high-quality visual context for Stage 3 image generation.

Do not include visual layout specs, color overrides, or design notes here.
All visual decisions are governed by `design.md`. The image generation step
in Stage 3 will receive both files together.

---

## Stage 3: Image Generation

With all Markdown files in place, generate a PNG image for every slide. Work
through each `slide_xx.md` one at a time.

> **Note on Text Rendering:**
> Image generation models (including Imagen) are continuously improving but may still occasionally render text with minor spelling or font inconsistencies, especially for complex layouts or non-English characters.
> - To ensure the slides have meaningful content, the generated prompt will explicitly include the actual titles and key points to be rendered.
> - If the rendered text is unsatisfactory, you can request a regeneration or planned to overlay the text digitally in a post-processing step.

For each slide:

1. **Load Files**: Read the entire content of `design.md` and the current `slide_xx.md`.
2. **Construct Prompt**: Combine the contents into a single prompt for the `generate_image` tool. Wrap each file's content in XML-like tags, and **prepend clear instructions** to guide the model on what to render (the Title) and what to use only as visual context (the Script). The prompt MUST follow this structure:

   ```markdown
   Generate a professional 16:9 widescreen (1920×1080 px) presentation slide image based on the design system and slide content below.
   - **DO** render the "Title" text from <slide_content> clearly on the slide, respecting the layout, typography, and colors defined in <design_system>.
   - **DO NOT** render the "Script" text literally; use it only as contextual inspiration to generate the background illustration or visual elements.

   <design_system>
   [Insert the entire content of design.md here]
   </design_system>

   <slide_content>
   [Insert the entire content of slide_xx.md here]
   </slide_content>
   ```

3. **Generate the image**: Call the `generate_image` tool with this combined prompt. Save the output as `slide_XX.png` (e.g. `slide_01.png`).

Repeat until all slides are generated. Then present the complete set to the user.

---

## Template Reference

| File | Purpose |
|---|---|
| `templates/design.md` | Visual system template — color, type, layout rules |
| `templates/outlines.md` | Full deck outline — slide list with types and summaries |
| `templates/slide_xx.md` | Per-slide content — title and spoken script |

Read the relevant template before generating each output type in Stage 2. The
templates contain field-by-field guidance and notes for adapting to different
content categories.

---

## Quality Principles

- **One idea per slide.** If a slide is trying to say two things, split it.
- **Visuals over text.** Prefer an illustration or a bold statistic over a
  paragraph. Slides are not documents.
- **Consistency.** Every slide must feel like it belongs to the same deck.
  The `design.md` file exists precisely to enforce this — refer back to it
  whenever you are unsure about a color, font, or layout choice.
- **Script Depth & Duration.** Aim for a natural 1–2 minute presentation per slide. The spoken script must be 150–300 words/characters and structured with a smooth transition followed by high-density elaboration (data, details, metaphors). A rich, concrete script gives the image model much stronger visual context to produce high-quality, customized slide images. Vague scripts produce generic visuals.
