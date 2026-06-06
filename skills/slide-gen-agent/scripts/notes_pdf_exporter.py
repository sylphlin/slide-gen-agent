import os
import sys
import glob
import re
import json

def register_unicode_font() -> str:
    """Finds and registers a Unicode-compatible font from the system to support multilingual speaker notes."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        # macOS
        ("/System/Library/Fonts/STHeiti Light.ttc", "STHeiti-Light"),
        ("/System/Library/Fonts/Supplemental/Songti.ttc", "Songti"),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "ArialUnicode"),
        ("/Library/Fonts/Arial Unicode.ttf", "ArialUnicode"),
        # Linux
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "WQY-MicroHei"),
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WQY-ZenHei"),
        ("/usr/share/fonts/truetype/droid/DroidSansFallback.ttf", "DroidSansFallback"),
        # Windows
        ("C:\\Windows\\Fonts\\msyh.ttc", "Microsoft-YaHei"),
        ("C:\\Windows\\Fonts\\simsun.ttc", "SimSun"),
    ]

    for path, name in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue

    return "Helvetica"  # Default fallback

def extract_title_and_script(md_path: str) -> tuple[str, str]:
    if not os.path.exists(md_path):
        return "", ""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        title = ""
        title_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
        script = ""
        script_match = re.search(r'## Script\s*([\s\S]*)', content)
        if script_match:
            script = script_match.group(1).strip()
        return title, script
    except Exception:
        return "", ""

def export_session_to_notes_pdf(session_path: str, pdf_file_name: str = None) -> dict:
    """Gathers all slide PNGs and compiles them into a PDF featuring slide images along with speaker notes."""
    slides_dir = os.path.join(session_path, 'slides')
    png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
    
    if not png_files:
        slides_dir = session_path
        png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
        
    if not png_files:
        raise ValueError(f"No slide PNG images found in {session_path}. Make sure to generate slide images first.")
        
    output_name = pdf_file_name or 'speaker_notes.pdf'
    if not output_name.endswith('.pdf'):
        output_name += '.pdf'
        
    output_path = os.path.join(session_path, output_name)
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    
    doc = SimpleDocTemplate(
        output_path, 
        pagesize=letter,
        rightMargin=0.5*inch, 
        leftMargin=0.5*inch,
        topMargin=0.5*inch, 
        bottomMargin=0.5*inch
    )
    
    styles = getSampleStyleSheet()
    font_name = register_unicode_font()
    
    title_style = ParagraphStyle(
        'SlideTitle',
        parent=styles['Heading2'],
        fontName=font_name,
        fontSize=16,
        leading=20,
        textColor='#333333',
        spaceAfter=12
    )
    
    notes_heading_style = ParagraphStyle(
        'NotesHeading',
        parent=styles['Heading3'],
        fontName=font_name,
        fontSize=13,
        leading=16,
        textColor='#007bff',
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'NotesBody',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=11,
        leading=16,
        textColor='#555555'
    )
    
    story = []
    
    for png_file in png_files:
        filename = os.path.basename(png_file)
        slide_num_match = re.search(r'slide_(\d+)\.png', filename)
        if not slide_num_match:
            continue
        pad_num = slide_num_match.group(1)
        
        md_file = os.path.join(session_path, f"slide_{pad_num}.md")
        slide_title, script_notes = extract_title_and_script(md_file)
        
        header_text = f"Slide {pad_num}"
        if slide_title:
            header_text += f": {slide_title}"
        story.append(Paragraph(header_text, title_style))
        
        img_width = 7.5 * inch
        img_height = 7.5 * (9/16) * inch
        story.append(Image(png_file, width=img_width, height=img_height))
        
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("<b>Speaker Notes:</b>", notes_heading_style))
        
        formatted_notes = script_notes.replace('\n', '<br/>') if script_notes else "(No speaker notes)"
        story.append(Paragraph(formatted_notes, body_style))
        story.append(PageBreak())
        
    doc.build(story)
    
    return {
        "message": f"Successfully compiled {len(png_files)} slides with speaker notes into a PDF document.",
        "pdfName": output_name,
        "pdfPath": output_path
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 notes_pdf_exporter.py <sessionPath> [pdfFileName]", file=sys.stderr)
        sys.exit(1)
        
    session_path_arg = sys.argv[1]
    pdf_name_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = export_session_to_notes_pdf(session_path_arg, pdf_name_arg)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(f"Speaker notes PDF compilation failed: {str(e)}", file=sys.stderr)
        sys.exit(1)
