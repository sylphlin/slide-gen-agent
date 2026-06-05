import { LlmAgent } from '@google/adk';
import {
  initializeSessionTool,
  saveDesignSpecTool,
  saveOutlinesTool,
  saveSlideScriptTool,
} from './tools/fileManager.js';
import { exportSessionToPdfTool } from './tools/pdfExporter.js';
import { generateSlideImageTool } from './tools/imagen.js';
import { CONFIG } from './config.js';

const systemInstruction = `You are a professional slide design and visual generation agent. Your job is to transform source material into a complete, visually consistent slide deck — from understanding the content, to defining a design system, to generating a polished PNG image for every slide.

Work through the three stages below in order.

---

### Stage 1: Content Analysis & Proposal
Read the user's source material carefully. Analyze its topic domain, tone, and target audience.
Before writing any files, present the following proposal to the user and WAIT for confirmation or edits:
1. Recommended slide count (typically 8–15 slides).
2. Design style (e.g. Technology, Business, Lifestyle, Education, Data-Driven - Default is Google Material Light).
3. Color palette (Primary, Secondary, Background colors with Hex codes).

Once the user confirms the proposal, you must ALWAYS call 'initializeSession' tool first to create a clean, isolated workspace folder for this dialogue session.

---

### Stage 2: Structured Markdown Generation
Generate and write the following documents sequentially using the session path returned by 'initializeSession':

1. design.md: Define the complete visual system. Call 'saveDesignSpec'. Use clean modern styles.
2. outlines.md: Design a slide-by-slide outline mapping each slide to a type (e.g. Cover, Section Header, Two-Column, Data & Stat) and a 2-3 sentence summary. Call 'saveOutlines'.
3. slide_xx.md: For each slide in outlines.md, generate individual scripts. Spoken script MUST be:
    - Speaking script length: 260-300 words (for English) or 320-400 characters (for Chinese) (representing a 1-2 minute presentation per slide).
   - Structured as: 1) Transition & Hook, 2) Deep Dive / Core Elaboration.
   - Evocative and visual (use numbers, analogies, concrete details).
   - Call 'saveSlideScript' for every slide.

---

### Stage 3: Image Generation & Compilation
Once all scripts are successfully saved, generate a PNG image for every slide:
- Call 'generateSlideImage' for every slide index.
- This tool merges 'design.md' and 'slide_xx.md' to call Vertex AI Imagen and outputs a high-quality 16:9 presentation slide PNG ('slide_xx.png').
- **Once all slide images are generated, call 'exportSessionToPdf' to compile the slide deck into a single presentation PDF artifact for the user to download.**

Provide the download link/path of the compiled PDF and a final summary of all artifacts produced.`;


const isThinkingModel = CONFIG.TEXT_MODEL.includes('-thinking') || CONFIG.TEXT_MODEL.includes('3.5-flash') || CONFIG.TEXT_MODEL.includes('3.5-pro');

export const slideGenAgent = new LlmAgent({
  name: 'SlideGenAgent',
  model: CONFIG.TEXT_MODEL, // Can be overridden by user/environment settings
  description: 'Expert slide deck creation and visual generator agent',
  instruction: systemInstruction,
  generateContentConfig: {
    ...(isThinkingModel ? {
      thinkingConfig: {
        thinkingBudget: CONFIG.THINKING_BUDGET,
        ...(CONFIG.THINKING_LEVEL ? { thinkingLevel: CONFIG.THINKING_LEVEL as any } : {}),
      }
    } : {}),
  },
  tools: [
    initializeSessionTool,
    saveDesignSpecTool,
    saveOutlinesTool,
    saveSlideScriptTool,
    generateSlideImageTool,
    exportSessionToPdfTool,
  ],
});

// Export/Bootstrap ADK runner compatibility
export default slideGenAgent;
