import * as fs from 'fs';
import * as path from 'path';

/**
 * Gathers all slide PNGs in the session slides directory and compiles them into a single PDF presentation.
 * @param sessionPath The absolute session path
 * @param pdfFileName Optional custom filename for the output PDF (defaults to presentation.pdf)
 */
export async function exportSessionToPdf(sessionPath: string, pdfFileName?: string): Promise<{ message: string; pdfName: string; pdfPath: string }> {
  // @ts-ignore
  const { PDFDocument } = await import('pdf-lib'); // Dynamic import to keep startup fast
  const slidesDir = path.join(sessionPath, 'slides');
  if (!fs.existsSync(slidesDir)) {
    throw new Error(`Slides directory does not exist: ${slidesDir}`);
  }

  // Read all files and filter for slide_xx.png files
  const files = fs.readdirSync(slidesDir);
  const pngFiles = files
    .filter(file => /^slide_\d+\.png$/.test(file))
    .sort(); // Sorts numerically (slide_01.png, slide_02.png, ...)

  if (pngFiles.length === 0) {
    throw new Error(`No slide PNG images found in ${slidesDir}. Make sure to generate slide images first.`);
  }

  const pdfDoc = await PDFDocument.create();

  for (const fileName of pngFiles) {
    const filePath = path.join(slidesDir, fileName);
    const pngImageBytes = fs.readFileSync(filePath);
    const pngImage = await pdfDoc.embedPng(pngImageBytes);

    // Embed each PNG image page with its native dimensions (typically 16:9 widescreen)
    const page = pdfDoc.addPage([pngImage.width, pngImage.height]);
    page.drawImage(pngImage, {
      x: 0,
      y: 0,
      width: pngImage.width,
      height: pngImage.height,
    });
  }

  const pdfBytes = await pdfDoc.save();
  const outputName = pdfFileName ? (pdfFileName.endsWith('.pdf') ? pdfFileName : `${pdfFileName}.pdf`) : 'presentation.pdf';
  const outputPath = path.join(sessionPath, outputName);

  fs.writeFileSync(outputPath, pdfBytes);

  return {
    message: `Successfully compiled ${pngFiles.length} slides into a single PDF presentation.`,
    pdfName: outputName,
    pdfPath: outputPath,
  };
}

// CLI Support (Allows running from Antigravity/Codex terminal directly)
if (typeof process !== 'undefined' && process.argv && process.argv[1] && (process.argv[1].endsWith('pdfExporter.ts') || process.argv[1].endsWith('pdfExporter.js'))) {
  const sessionPathArg = process.argv[2];
  const pdfNameArg = process.argv[3];
  if (!sessionPathArg) {
    console.error('Usage: node pdfExporter.js <sessionPath> [pdfFileName]');
    process.exit(1);
  }
  exportSessionToPdf(sessionPathArg, pdfNameArg)
    .then(result => {
      console.log(JSON.stringify(result, null, 2));
      process.exit(0);
    })
    .catch(err => {
      console.error('PDF compilation failed:', err.message);
      process.exit(1);
    });
}
