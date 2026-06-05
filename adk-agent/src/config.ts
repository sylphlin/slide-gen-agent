/**
 * Host ADK Agent Configuration
 */
export const CONFIG = {
  // GCP Credentials & Locations
  GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT || 'your-gcp-project-id',
  GOOGLE_CLOUD_LOCATION: process.env.GOOGLE_CLOUD_LOCATION || 'us-central1',
  RESOURCES_BUCKET: process.env.RESOURCES_BUCKET || 'your-gcp-project-id-bucket',

  // Model selection
  TEXT_MODEL: process.env.TEXT_MODEL || 'gemini-3.5-flash',
  IMAGEN_MODEL: process.env.IMAGEN_MODEL || 'imagen-3.0-generate-002',

  // Thinking settings
  THINKING_LEVEL: process.env.THINKING_LEVEL || 'high',
  THINKING_BUDGET: process.env.THINKING_BUDGET ? parseInt(process.env.THINKING_BUDGET) : 2048,
};

// Set output session directory in the environment for tools to use
process.env.SESSION_OUTPUT_DIR = process.env.SESSION_OUTPUT_DIR || 'artifacts';
