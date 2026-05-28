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
the Slide Structure Defaults in `design.md`), and a one-sentence content summary.
The summary is the seed for each `slide_xx.md` — make it specific enough to
generate real content from.

### Step 3 — `slide_01.md` through `slide_XX.md`

Generate one file per slide, following `templates/slide_xx.md`. The most
important field in each file is **Visual Description** — write it as a detailed,
self-contained scene description that an image model can act on directly. Include:
- The layout type (e.g. left image / right text, centered hero)
- What visual element to show (illustration, chart, photo, icon, abstract shape)
- Color references from `design.md`
- Art style (default: flat design, Google Material style, clean white background)

Every other field (title, bullets, hero text) feeds into the prompt as
overlay text or compositional context.

---

## Stage 3: Image Generation

With all Markdown files in place, generate a PNG image for every slide. Work
through each `slide_xx.md` one at a time.

> **Important — Text Rendering Limitation:**
> Image generation models (including Imagen) render background visuals and layout
> well, but are unreliable at rendering accurate text — especially for CJK
> characters (Chinese, Japanese, Korean). To get clean results:
> - The image prompt should focus on **background, composition, color, and visual
>   elements** — not on rendering the actual slide text.
> - Describe text elements (title, bullets) by their **position and style only**
>   (e.g. "space reserved for a bold left-aligned title in the upper-left zone"),
>   not their literal content.
> - Slide text should be applied as an **overlay layer** after image generation —
>   either by the user in their presentation tool (Google Slides, Keynote, etc.),
>   or by a post-processing step.
> - This approach produces sharper, more consistent results regardless of language.

For each slide:

1. **Read `design.md`** to load the global visual rules (palette, typography,
   layout defaults).
2. **Read the current `slide_xx.md`** to get the slide-specific content and
   visual description.
3. **Compose an image generation prompt** that combines both sources into a
   single, detailed English description. A strong prompt includes:
   - Slide dimensions and aspect ratio: **1920×1080 px, 16:9**
   - Layout type and composition (from Visual Layout in `slide_xx.md`)
   - Background color (from `design.md`)
   - **Text zones** — describe reserved areas by position and visual weight only,
     e.g. "upper-left zone with a clean empty area for a bold title" or
     "centered empty space for a large hero number". Do NOT include the actual
     text content — it will be added as an overlay after generation.
   - The visual element (illustration, chart, photo) described vividly
   - Color palette (primary, secondary, accent hex codes from `design.md`)
   - Art style: flat design, Google Material aesthetic, clean and professional
   - Any slide-specific color overrides or design notes

4. **Generate the image** using your image generation capability. Save or
   label the output as `slide_XX.png` (e.g. `slide_01.png`, `slide_02.png`).

Repeat until all slides are generated. Then present the complete set to the user.

---

## Template Reference

| File | Purpose |
|---|---|
| `templates/design.md` | Visual system template — color, type, layout rules |
| `templates/outlines.md` | Full deck outline — slide list with types and summaries |
| `templates/slide_xx.md` | Per-slide detail — content, layout, visual description |

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
- **Specificity in prompts.** Vague image prompts produce generic results.
  Invest time in the Visual Description field — it directly determines image quality.
