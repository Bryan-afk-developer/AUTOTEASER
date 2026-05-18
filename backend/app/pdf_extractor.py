"""
AutoTeaser - PDF Text Extractor
Uses pdfplumber to extract text from PDF bank statements.
"""
import pdfplumber
from pathlib import Path


def extract_text(pdf_path: str | Path) -> dict:
    """
    Extract all text from a PDF file using pdfplumber.
    
    Returns:
        dict with keys: full_text, pages (list of page texts), page_count
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    pages_text = []
    
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
    
    full_text = "\n\n".join(pages_text)
    
    return {
        "full_text": full_text,
        "pages": pages_text,
        "page_count": len(pages_text),
    }
