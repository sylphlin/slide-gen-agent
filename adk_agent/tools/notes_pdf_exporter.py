import os
import glob
import re
from google.adk.tools.tool_context import ToolContext
from google.genai.types import Part

try:
    from ..config import save_artifact_helper
except ImportError:
    from config import save_artifact_helper

# Bundled WQY MicroHei — TrueType CJK font covering Simplified Chinese, Traditional Chinese, Japanese
_BUNDLED_FONT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets', 'fonts', 'wqy-microhei.ttc'
)


def register_unicode_font() -> str:
    """Registers a CJK-capable font with reportlab. Tries the bundled WQY MicroHei first,
    then falls back to common system fonts, then to Helvetica (Latin-only)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # 1. Bundled WQY MicroHei (TrueType, compatible with reportlab)
    if os.path.exists(_BUNDLED_FONT):
        for idx in range(3):
            try:
                pdfmetrics.registerFont(TTFont('WQYMicroHei', _BUNDLED_FONT, subfontIndex=idx))
                return 'WQYMicroHei'
            except Exception:
                continue

    # 2. System font fallbacks
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

    return "Helvetica"


def extract_title_and_script(md_path: str) -> tuple[str, str]:
    """Extracts the slide title and speaker notes from the slide's markdown file."""
    if not os.path.exists(md_path):
        return "", ""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract title under the # heading
        title = ""
        title_match = re.search(r'^#\s+(.*)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            
        # Extract script notes under ## Script
        script = ""
        script_match = re.search(r'## Script\s*([\s\S]*)', content)
        if script_match:
            script = script_match.group(1).strip()
            
        return title, script
    except Exception:
        return "", ""


async def export_speaker_notes_pdf(session_path: str, tool_context: ToolContext) -> str:
    """Compiles a PDF document containing each slide's image followed by its title and speaker notes.
    This is similar to the layout of the preview.html page.
    
    Args:
        session_path: The absolute session path returned by initialize_session
        tool_context: The tool context injected by the framework
    """
    # Search in 'slides/' subfolder first
    slides_dir = os.path.join(session_path, 'slides')
    png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
    
    # Fallback to session root directory if subfolder is empty
    if not png_files:
        slides_dir = session_path
        png_files = sorted(glob.glob(os.path.join(slides_dir, 'slide_*.png')))
        
    if not png_files:
        return "Error: No slide PNG images found in the session. Generate images first."
        
    pdf_path = os.path.join(session_path, 'speaker_notes.pdf')
    
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        # Initialize document with 0.5 inch margins
        doc = SimpleDocTemplate(
            pdf_path, 
            pagesize=letter,
            rightMargin=0.5*inch, 
            leftMargin=0.5*inch,
            topMargin=0.5*inch, 
            bottomMargin=0.5*inch
        )
        
        styles = getSampleStyleSheet()
        font_name = register_unicode_font()
        
        # Custom paragraph styles using the resolved font
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
            
            # Extract slide details
            md_file = os.path.join(session_path, f"slide_{pad_num}.md")
            slide_title, script_notes = extract_title_and_script(md_file)
            
            # 1. Slide Header
            header_text = f"Slide {pad_num}"
            if slide_title:
                header_text += f": {slide_title}"
            story.append(Paragraph(header_text, title_style))
            
            # 2. Slide Image (scaled to fit the page width of 7.5 inches)
            img_width = 7.5 * inch
            img_height = 7.5 * (9/16) * inch  # Widescreen aspect ratio (16:9)
            story.append(Image(png_file, width=img_width, height=img_height))
            
            story.append(Spacer(1, 0.2*inch))
            
            # 3. Speaker Notes
            story.append(Paragraph("<b>Speaker Notes:</b>", notes_heading_style))
            
            # Format newlines in notes to HTML break tags for reportlab Paragraph
            formatted_notes = script_notes.replace('\n', '<br/>') if script_notes else "(No speaker notes)"
            story.append(Paragraph(formatted_notes, body_style))
            
            # 4. Page Break for the next slide
            story.append(PageBreak())
            
        # Build document
        doc.build(story)
        
        # Read the generated PDF bytes to save as artifact
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
            
        artifact_part = Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        await save_artifact_helper('speaker_notes.pdf', artifact_part, tool_context)
        
        try:
            from ..config import get_gcs_artifact_url
        except ImportError:
            from config import get_gcs_artifact_url
            
        gcs_url = get_gcs_artifact_url('speaker_notes.pdf', tool_context)
        if gcs_url:
            return f"Speaker notes PDF successfully compiled.\nDownload it here: {gcs_url}"
            
        return f"Speaker notes PDF successfully compiled and saved to {pdf_path}"
        
    except Exception as e:
        return f"Failed to export speaker notes PDF: {str(e)}"
