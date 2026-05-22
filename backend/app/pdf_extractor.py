"""
AutoTeaser - PDF Text Extractor
Uses PyMuPDF (fitz) for high-fidelity text extraction, falling back to pdfplumber.
"""
import fitz
import pdfplumber
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def extract_text(pdf_path: str | Path) -> dict:
    """
    Extract all text from a PDF file using PyMuPDF (fitz), with pdfplumber fallback.
    
    Returns:
        dict with keys: full_text, pages (list of page texts), page_count
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    pages_text = []
    
    try:
        # Try PyMuPDF first (much more robust at reading native PDFs with encoding issues)
        doc = fitz.open(str(pdf_path))
        for page in doc:
            text = page.get_text("text") or ""
            pages_text.append(text)
        doc.close()
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed, falling back to pdfplumber: {e}")
        pages_text = []

    # If PyMuPDF failed or returned no text, fallback to pdfplumber
    if not pages_text or sum(len(p.strip()) for p in pages_text) < 50:
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
