import os
import sys
import glob
import json
from PIL import Image

def export_session_to_pdf(session_path: str, pdf_file_name: str = None) -> dict:
    """Gathers all slide PNGs and compiles them into a single PDF presentation.
    Supports both subfolder 'slides/' and root session directory structures.
    """
    # 1. Search in 'slides/' subfolder first
    slides_dir = os.path.join(session_path, 'slides')
    png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
    
    # 2. Fallback to session root directory if subfolder is empty
    if not png_files:
        slides_dir = session_path
        png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
        
    if not png_files:
        raise ValueError(f"No slide PNG images found in {session_path}. Make sure to generate slide images first.")
        
    # Open and convert to RGB
    images = [Image.open(f).convert('RGB') for f in png_files]
    
    # Resolve output name
    output_name = pdf_file_name or 'presentation.pdf'
    if not output_name.endswith('.pdf'):
        output_name += '.pdf'
        
    output_path = os.path.join(session_path, output_name)
    
    # Compile
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:]
    )
    
    return {
        "message": f"Successfully compiled {len(png_files)} slides into a single PDF presentation.",
        "pdfName": output_name,
        "pdfPath": output_path
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 pdf_exporter.py <sessionPath> [pdfFileName]", file=sys.stderr)
        sys.exit(1)
        
    session_path_arg = sys.argv[1]
    pdf_name_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = export_session_to_pdf(session_path_arg, pdf_name_arg)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"PDF compilation failed: {str(e)}", file=sys.stderr)
        sys.exit(1)
