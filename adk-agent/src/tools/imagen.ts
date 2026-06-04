import { FunctionTool } from '@google/adk';
import { z } from 'zod';
import * as fs from 'fs';
import * as path from 'path';
import { PredictionServiceClient, helpers } from '@google-cloud/aiplatform';

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
  execute: async ({ sessionPath, slideNumber }) => {
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
      const project = process.env.GOOGLE_CLOUD_PROJECT;
      const location = process.env.GOOGLE_CLOUD_LOCATION || 'us-central1';
      const imagenModel = process.env.IMAGEN_MODEL || 'imagen-3.0-generate-002';

      if (!project) {
        throw new Error('GOOGLE_CLOUD_PROJECT is not configured. Please set the GOOGLE_CLOUD_PROJECT environment variable.');
      }

      // Create the client using Location-specific Endpoint
      const client = new PredictionServiceClient({
        apiEndpoint: `${location}-aiplatform.googleapis.com`,
      });

      // Formulate endpoint string
      const endpoint = `projects/${project}/locations/${location}/publishers/google/models/${imagenModel}`;

      const instance = { prompt: mergedPrompt };
      const parameter = {
        sampleCount: 1,
        aspectRatio: '16:9',
        outputMimeType: 'image/png',
      };

      const instanceValue = helpers.toValue(instance);
      const parameterValue = helpers.toValue(parameter);

      if (!instanceValue || !parameterValue) {
        throw new Error('Failed to format predict parameters for Imagen.');
      }

      const [response] = await client.predict({
        endpoint,
        instances: [instanceValue],
        parameters: parameterValue,
      });

      const base64Data = response.predictions?.[0]?.structValue?.fields?.bytesBase64Encoded?.stringValue;
      if (!base64Data) {
        throw new Error('Imagen API response did not contain any generated image bytes.');
      }

      fs.writeFileSync(outputPath, Buffer.from(base64Data, 'base64'));
      return `Successfully generated image for Slide ${padNum} and saved to ${outputPath}`;
    } catch (error: any) {
      return `Failed to generate image for Slide ${padNum}: ${error.message}`;
    }
  },
});


