import * as fs from 'fs';
import * as path from 'path';

/**
 * Generates an HTML preview page listing all generated slide PNGs.
 * @param sessionPath The absolute session path
 */
export async function generatePreviewPage(sessionPath: string): Promise<string> {
  const slidesDir = path.join(sessionPath, 'slides');
  if (!fs.existsSync(slidesDir)) {
    throw new Error(`Slides directory does not exist: ${slidesDir}`);
  }

  // Find all png files in the slides directory, sorted numerically
  const files = fs.readdirSync(slidesDir);
  const pngFiles = files
    .filter(f => f.startsWith('slide_') && f.endsWith('.png'))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

  if (pngFiles.length === 0) {
    return 'No slide PNG images found to preview.';
  }

  let cardsHtml = '';
  for (const file of pngFiles) {
    const padNum = file.replace('slide_', '').replace('.png', '');
    cardsHtml += `
    <div class="slide-card">
      <div class="slide-header">Slide ${padNum}</div>
      <img class="slide-img" src="slides/${file}" alt="Slide ${padNum}">
    </div>`;
  }

  const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Presentation Deck Preview</title>
  <style>
    body {
      font-family: 'Google Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: #f8f9fa;
      color: #202124;
      margin: 0;
      padding: 40px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    h1 {
      margin-bottom: 30px;
      font-size: 28px;
      font-weight: 500;
    }
    .deck-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 40px;
      width: 100%;
      max-width: 960px;
    }
    .slide-card {
      background: #ffffff;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
      width: 100%;
      box-sizing: border-box;
    }
    .slide-header {
      font-size: 16px;
      font-weight: 500;
      color: #5f6368;
      margin-bottom: 12px;
      border-bottom: 1px solid #f1f3f4;
      padding-bottom: 8px;
    }
    .slide-img {
      width: 100%;
      height: auto;
      aspect-ratio: 16/9;
      border: 1px solid #e8eaed;
      border-radius: 4px;
      display: block;
    }
  </style>
</head>
<body>
  <h1>Presentation Deck Preview</h1>
  <div class="deck-container">${cardsHtml}
  </div>
</body>
</html>`;

  const outputPath = path.join(sessionPath, 'preview.html');
  fs.writeFileSync(outputPath, htmlContent, 'utf-8');

  return `Successfully generated preview page: ${outputPath}`;
}

// CLI Support (Allows running from terminal directly)
if (typeof process !== 'undefined' && process.argv && process.argv[1] && (process.argv[1].endsWith('previewGenerator.ts') || process.argv[1].endsWith('previewGenerator.js'))) {
  const sessionPathArg = process.argv[2];
  if (!sessionPathArg) {
    console.error('Usage: node previewGenerator.js <sessionPath>');
    process.exit(1);
  }
  generatePreviewPage(sessionPathArg)
    .then(result => {
      console.log(result);
      process.exit(0);
    })
    .catch(err => {
      console.error('Preview generation failed:', err.message);
      process.exit(1);
    });
}
