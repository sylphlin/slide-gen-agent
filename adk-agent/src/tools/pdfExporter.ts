import { FunctionTool, Context } from '@google/adk';
import { z } from 'zod';
import { exportSessionToPdf } from './compiled_skills/pdfExporter.js';

/**
 * Tool: exportSessionToPdf
 * Gathers all slide PNGs in the session slides directory and compiles them into a single PDF presentation.
 */
export const exportSessionToPdfTool = new FunctionTool({
  name: 'exportSessionToPdf',
  description: 'Gathers all generated slide PNG images in the active session, merges them in numeric order into a single PDF presentation, and saves it in the session directory as an artifact for the user to download.',
  parameters: z.object({
    sessionPath: z.string().describe('The absolute session path returned by initializeSession'),
    pdfFileName: z.string().optional().describe('Optional custom filename for the output PDF (defaults to presentation.pdf)'),
  }),
  execute: async ({ sessionPath, pdfFileName }, tool_context) => {
    try {
      const result = await exportSessionToPdf(sessionPath, pdfFileName, tool_context);
      return JSON.stringify(result);
    } catch (error: any) {
      throw new Error(`PDF compilation failed: ${error.message}`);
    }
  },
});
