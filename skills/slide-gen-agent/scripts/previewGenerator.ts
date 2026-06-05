import * as fs from 'fs';
import * as path from 'path';

/**
 * Generates an HTML preview page listing all generated slide PNGs.
 * @param sessionPath The absolute session path
 * @param tool_context Optional ADK context to register the artifact
 */
export async function generatePreviewPage(sessionPath: string, tool_context?: any): Promise<string> {
  // Find all png files in the session root directory, sorted numerically
  const files = fs.readdirSync(sessionPath);
  const pngFiles = files
    .filter(f => f.startsWith('slide_') && f.endsWith('.png'))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }));

  if (pngFiles.length === 0) {
    return 'No slide PNG images found to preview.';
  }

  let cardsHtml = '';
  for (const file of pngFiles) {
    const padNum = file.replace('slide_', '').replace('.png', '');
    const imgPath = path.join(sessionPath, file);
    
    // Read local PNG file bytes and convert to Base64
    const imgBase64 = fs.readFileSync(imgPath).toString('base64');
    
    // Parse speaker notes script if md file exists
    let notesHtml = '';
    const mdPath = path.join(sessionPath, `slide_${padNum}.md`);
    if (fs.existsSync(mdPath)) {
      const mdContent = fs.readFileSync(mdPath, 'utf-8');
      const scriptMatch = mdContent.split(/##\s+Script\r?\n/);
      const scriptText = scriptMatch[1] ? scriptMatch[1].trim() : mdContent.trim();
      
      const formattedScript = scriptText
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
        .map(line => `<p>${line}</p>`)
        .join('');
        
      notesHtml = `
      <div class="slide-notes">
        <div class="notes-label">🗣️ Speaker Notes:</div>
        <div class="notes-content">${formattedScript}</div>
      </div>`;
    }

    cardsHtml += `
    <div class="slide-card">
      <div class="slide-header">Slide ${padNum}</div>
      <img class="slide-img" src="data:image/png;base64,${imgBase64}" alt="Slide ${padNum}">
      ${notesHtml}
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
      gap: 45px;
      width: 100%;
      max-width: 960px;
    }
    .slide-card {
      background: #ffffff;
      border: 1px solid #dadce0;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
      width: 100%;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .slide-header {
      font-size: 16px;
      font-weight: 500;
      color: #5f6368;
      margin-bottom: 4px;
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
    .slide-notes {
      background-color: #f1f3f4;
      border-left: 4px solid #1a73e8;
      border-radius: 4px;
      padding: 14px 18px;
      text-align: left;
    }
    .notes-label {
      font-size: 13px;
      font-weight: 500;
      color: #1a73e8;
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .notes-content {
      font-size: 15px;
      line-height: 1.6;
      color: #3c4043;
    }
    .notes-content p {
      margin: 0 0 8px 0;
    }
    .notes-content p:last-child {
      margin-bottom: 0;
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

  if (tool_context) {
    await tool_context.saveArtifact('preview.html', {
      inlineData: {
        data: Buffer.from(htmlContent).toString('base64'),
        mimeType: 'text/html',
      }
    });
  }

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
