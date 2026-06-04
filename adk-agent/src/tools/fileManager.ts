import { FunctionTool } from '@google/adk';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Helper to ensure directories exist
 */
function ensureDirExist(dirPath: string) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Tool: initializeSession
 * Creates an isolated session folder to prevent dialogue/state pollution.
 */
export const initializeSessionTool = new FunctionTool({
  name: 'initializeSession',
  description: 'Initializes a new slide deck session. Creates a dedicated folder and returns its absolute path. ALWAYS call this first before writing any slide files.',
  parameters: z.object({
    projectName: z.string().describe('A short name for the presentation (e.g. tech-trends)'),
  }),
  execute: async ({ projectName }) => {
    const cleanName = projectName.toLowerCase().replace(/[^a-z0-9-_]/g, '-');
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').substring(0, 12);
    const sessionId = `session_${cleanName}_${timestamp}`;
    const baseOutputDir = process.env.SESSION_OUTPUT_DIR || path.join(process.cwd(), 'artifacts');
    const sessionPath = path.join(baseOutputDir, sessionId);

    ensureDirExist(sessionPath);
    ensureDirExist(path.join(sessionPath, 'slides')); // Subfolder for individual slides

    return JSON.stringify({
      message: 'Session successfully initialized.',
      sessionId,
      sessionPath,
    });
  },
});

/**
 * Tool: saveDesignSpec
 * Saves the customized design.md specification into the session directory.
 */
export const saveDesignSpecTool = new FunctionTool({
  name: 'saveDesignSpec',
  description: 'Saves the customized design.md style specifications to the active session directory.',
  parameters: z.object({
    sessionPath: z.string().describe('The absolute session path returned by initializeSession'),
    designSpecContent: z.string().describe('The full Markdown design specification details'),
  }),
  execute: async ({ sessionPath, designSpecContent }) => {
    const filePath = path.join(sessionPath, 'design.md');
    fs.writeFileSync(filePath, designSpecContent, 'utf-8');
    return `Design specification successfully written to ${filePath}`;
  },
});

/**
 * Tool: saveOutlines
 * Saves the full slide-by-slide deck outline.
 */
export const saveOutlinesTool = new FunctionTool({
  name: 'saveOutlines',
  description: 'Saves the complete outlines.md file to the active session directory.',
  parameters: z.object({
    sessionPath: z.string().describe('The absolute session path returned by initializeSession'),
    outlinesContent: z.string().describe('The full Markdown outline containing the slide table, types, and summaries'),
  }),
  execute: async ({ sessionPath, outlinesContent }) => {
    const filePath = path.join(sessionPath, 'outlines.md');
    fs.writeFileSync(filePath, outlinesContent, 'utf-8');
    return `Deck outlines successfully written to ${filePath}`;
  },
});

/**
 * Tool: saveSlideScript
 * Saves a single slide metadata, title, and transition/spoken script.
 */
export const saveSlideScriptTool = new FunctionTool({
  name: 'saveSlideScript',
  description: 'Saves an individual slide script (slide_xx.md) with transition and spoken script content.',
  parameters: z.object({
    sessionPath: z.string().describe('The absolute session path returned by initializeSession'),
    slideNumber: z.number().int().describe('The 1-indexed slide number (e.g. 1, 2, 3)'),
    slideType: z.string().describe('Layout type of the slide (e.g. Cover, Section Header, Two-Column, Data & Stat)'),
    title: z.string().describe('The slide header/title text to render on the image'),
    script: z.string().describe('The 150-300 character transition and spoken script'),
  }),
  execute: async ({ sessionPath, slideNumber, slideType, title, script }) => {
    const padNum = String(slideNumber).padStart(2, '0');
    const filePath = path.join(sessionPath, 'slides', `slide_${padNum}.md`);
    
    const fileContent = `---
slide_number: ${slideNumber}
slide_type: "${slideType}"
---

# ${title}

## Script

${script}
`;

    fs.writeFileSync(filePath, fileContent, 'utf-8');
    return `Slide ${padNum} script successfully written to ${filePath}`;
  },
});


