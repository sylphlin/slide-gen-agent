import { PredictionServiceClient } from '@google-cloud/aiplatform';
import { helpers } from '@google-cloud/aiplatform';
import { CONFIG } from '../config.js';

/**
 * Invokes Google Cloud Vertex AI Imagen to generate a slide image.
 * @param prompt The fully-formed multi-line prompt containing design specs and slide content
 * @returns Base64-encoded PNG string
 */
export async function generateImageFromVertex(prompt: string): Promise<string> {
  if (!CONFIG.GOOGLE_CLOUD_PROJECT || CONFIG.GOOGLE_CLOUD_PROJECT === 'your-gcp-project-id') {
    throw new Error('GOOGLE_CLOUD_PROJECT is not configured. Please set the GOOGLE_CLOUD_PROJECT environment variable.');
  }

  // Create the client using Location-specific Endpoint
  const client = new PredictionServiceClient({
    apiEndpoint: `${CONFIG.GCP_LOCATION}-aiplatform.googleapis.com`,
  });

  // Formulate endpoint string
  const endpoint = `projects/${CONFIG.GOOGLE_CLOUD_PROJECT}/locations/${CONFIG.GCP_LOCATION}/publishers/google/models/${CONFIG.IMAGEN_MODEL}`;

  // Format instances and parameters using helper tools from SDK
  const instance = {
    prompt: prompt,
  };

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

  const base64Image = response.predictions?.[0]?.structValue?.fields?.bytesBase64Encoded?.stringValue;
  if (!base64Image) {
    throw new Error('Imagen API response did not contain any generated image bytes.');
  }

  return base64Image;
}
