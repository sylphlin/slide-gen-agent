import { Storage } from '@google-cloud/storage';
import { CONFIG } from '../config.js';

// Initialize GCS client
const storage = new Storage({
  projectId: CONFIG.GOOGLE_CLOUD_PROJECT,
});

/**
 * Uploads a local file to the configured GCS bucket and returns its authenticated URL.
 * Falls back to throwing an error if the bucket is not configured or upload fails.
 */
export async function uploadToGCS(localFilePath: string, destinationPath: string): Promise<string> {
  if (!CONFIG.RESOURCES_BUCKET) {
    throw new Error('RESOURCES_BUCKET is not configured in config.ts or environment variables.');
  }

  // Clean bucket name (remove gs:// prefix if present)
  const bucketName = CONFIG.RESOURCES_BUCKET.replace(/^gs:\/\//, '');
  const bucket = storage.bucket(bucketName);


  await bucket.upload(localFilePath, {
    destination: destinationPath,
    metadata: {
      cacheControl: 'public, max-age=3600', // Cache for 1 hour
    },
  });

  // Standard browser-authenticated GCS download URL.
  // Users authenticated with GCP credentials for the project will be able to view/download this securely.
  return `https://storage.cloud.google.com/${bucketName}/${destinationPath}`;
}
