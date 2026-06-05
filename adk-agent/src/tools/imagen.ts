import { FunctionTool, Context } from '@google/adk';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';
import { GoogleGenAI } from '@google/genai';
import { CONFIG } from '../config.js';

// Initialize the GoogleGenAI SDK client.
// Since config.ts sets process.env.GOOGLE_GENAI_USE_VERTEXAI = 'true' and exports the project/location variables,
// this client will run in Vertex AI mode with proper authentication and endpoints.
const ai = new GoogleGenAI({});

/**
 * Tool: generateSlideImage
 * Merges design specifications + slide script and triggers high-quality slide image generation.
 */
export const generateSlideImageTool = new FunctionTool({
  name: 'generateSlideImage',
  description: 'Reads the generated design.md and an individual slide_xx.md, merges them into a highly contextual prompt, and uses Vertex AI Imagen to output slide_xx.png in the session slides directory.',
  parameters: z.object({
    sessionPath: z.string().describe('The absolute session path returned by initializeSession'),
    slideNumber: z.number().int().describe('The 1-indexed slide number to generate the image for'),
  }),
  execute: async ({ sessionPath, slideNumber }, tool_context) => {
    const padNum = String(slideNumber).padStart(2, '0');
    
    const designPath = path.join(sessionPath, 'design.md');
    const slidePath = path.join(sessionPath, 'slides', `slide_${padNum}.md`);
    const outputPath = path.join(sessionPath, 'slides', `slide_${padNum}.png`);

    // Validation
    if (!fs.existsSync(designPath)) {
      throw new Error(`Missing design specification: ${designPath}. Make sure to generate and save design.md first.`);
    }
    if (!fs.existsSync(slidePath)) {
      throw new Error(`Missing slide content file: ${slidePath}. Make sure to generate and save slide_${padNum}.md first.`);
    }

    const designContent = fs.readFileSync(designPath, 'utf-8');
    const slideContent = fs.readFileSync(slidePath, 'utf-8');

    // Construct merged XML-style prompt as defined in slide-gen-agent SKILL.md
    const mergedPrompt = `Generate a professional 16:9 widescreen (1920×1080 px) presentation slide image based on the design system and slide content below.
- **DO** render the "Title" text from <slide_content> clearly on the slide, respecting the layout, typography, and colors defined in <design_system>.
- **DO NOT** render the "Script" text literally; use it only as contextual inspiration to generate the background illustration or visual elements.

<design_system>
${designContent}
</design_system>

<slide_content>
${slideContent}
</slide_content>`;

    try {
      const project = CONFIG.GOOGLE_CLOUD_PROJECT;
      if (!project || project === 'your-gcp-project-id') {
        throw new Error('GOOGLE_CLOUD_PROJECT is not configured. Please set the GOOGLE_CLOUD_PROJECT environment variable.');
      }

      const isGeminiImageModel = CONFIG.IMAGEN_MODEL.startsWith('gemini-');
      let base64Data: string | undefined;

      if (isGeminiImageModel) {
        // Gemini image models must be called via generateContent with responseModalities
        const response = await ai.models.generateContent({
          model: CONFIG.IMAGEN_MODEL,
          contents: mergedPrompt,
          config: {
            responseModalities: ['IMAGE'],
          },
        });

        const parts = response.candidates?.[0]?.content?.parts;
        const imagePart = parts?.find(p => p.inlineData?.mimeType?.startsWith('image/'));
        base64Data = imagePart?.inlineData?.data;
      } else {
        // Traditional Imagen models must be called via generateImages
        const response = await ai.models.generateImages({
          model: CONFIG.IMAGEN_MODEL,
          prompt: mergedPrompt,
          config: {
            numberOfImages: 1,
            aspectRatio: '16:9',
            outputMimeType: 'image/png',
          },
        });

        base64Data = response.generatedImages?.[0]?.image?.imageBytes;
      }

      if (!base64Data) {
        throw new Error('Image generation response did not contain any generated image bytes.');
      }

      fs.writeFileSync(outputPath, Buffer.from(base64Data, 'base64'));

      if (tool_context) {
        await tool_context.saveArtifact(`slides/slide_${padNum}.png`, {
          inlineData: {
            data: base64Data,
            mimeType: 'image/png',
          }
        });
      }

      return `Successfully generated image for Slide ${padNum} and saved to ${outputPath}`;
    } catch (error: any) {
      return `Failed to generate image for Slide ${padNum}: ${error.message}`;
    }
  },
});
