import * as path from 'path';

export const CONFIG = {
  // Root paths
  WORKSPACE_ROOT: path.resolve(__dirname, '../../'),
  TEMPLATES_DIR: path.resolve(__dirname, '../../templates'),
  OUTPUT_DIR: path.resolve(__dirname, '../output'),

  // GCP / Vertex AI Settings
  GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT || 'your-gcp-project-id',
  GCP_LOCATION: process.env.GCP_LOCATION || 'us-central1',
  GCS_BUCKET: process.env.GCS_BUCKET || process.env.GOOGLE_CLOUD_BUCKET || '',
  IMAGEN_MODEL: 'gemini-3.1-flash-image',
  TEXT_MODEL: 'gemini-3.5-flash',
  THINKING_LEVEL: 'HIGH',
  THINKING_BUDGET: 2048,
};

