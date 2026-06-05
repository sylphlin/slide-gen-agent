/**
 * Host ADK Agent Configuration
 */
import * as path from 'path';

export const CONFIG = {
  // GCP Credentials & Locations
  GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT,
  GOOGLE_CLOUD_LOCATION: process.env.GOOGLE_CLOUD_LOCATION || 'global',
  IMAGEN_LOCATION: process.env.IMAGEN_LOCATION,

  // Model selection
  TEXT_MODEL: process.env.TEXT_MODEL || 'gemini-3.5-flash',
  IMAGEN_MODEL: process.env.IMAGEN_MODEL || 'gemini-3.1-flash-image',

  // Thinking settings
  THINKING_LEVEL: process.env.THINKING_LEVEL || 'high',
  THINKING_BUDGET: process.env.THINKING_BUDGET ? parseInt(process.env.THINKING_BUDGET) : 2048,
};

// Normalize and auto-fill image generation endpoint location
if (!CONFIG.IMAGEN_LOCATION) {
  const isGlobalImagen = CONFIG.IMAGEN_MODEL.startsWith('gemini-');
  CONFIG.IMAGEN_LOCATION = CONFIG.GOOGLE_CLOUD_LOCATION === 'global' && !isGlobalImagen
    ? 'us-central1'
    : CONFIG.GOOGLE_CLOUD_LOCATION;
}

// Set output session directory in the environment for tools to use.
// Ensure it resolves to the local adk-agent/artifacts directory (which is expected by adk web)
if (!process.env.SESSION_OUTPUT_DIR) {
  const cwd = process.cwd();
  const adkAgentDir = cwd.endsWith('adk-agent') ? cwd : path.join(cwd, 'adk-agent');
  process.env.SESSION_OUTPUT_DIR = path.join(adkAgentDir, 'artifacts');
}

// Force Gen AI SDK to use Vertex AI mode (Gemini Enterprise)
process.env.GOOGLE_GENAI_USE_VERTEXAI = 'true';

// Inject credentials/locations into process.env to auto-configure @google/genai SDK
if (CONFIG.GOOGLE_CLOUD_PROJECT) {
  process.env.GOOGLE_CLOUD_PROJECT = CONFIG.GOOGLE_CLOUD_PROJECT;
}
process.env.GOOGLE_CLOUD_LOCATION = CONFIG.GOOGLE_CLOUD_LOCATION;
process.env.IMAGEN_LOCATION = CONFIG.IMAGEN_LOCATION;
