"""
AutoTeaser - Bank Detector
Uses filename heuristics and text-based patterns to identify the bank.
Gemini Vision is NOT used — pure text extraction only.
"""
import logging
from pathlib import Path

import fitz  # PyMuPDF
import google.generativeai as genai

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# The 9 valid banks for this project
VALID_BANKS = ["hsbc", "bbva", "banorte", "santander", "scotiabank", "banamex", "inbursa", "sabadell", "bxplus"]


# ── Text-based detection ─────────────────────────────────────────────────────

# Structural patterns unique to each bank's format (NOT bank names in transactions)
# Highly specific signatures go first to prevent false matches in transaction text of other banks.
TEXT_FALLBACK_PATTERNS = [
    ("bxplus", ["bvm951002lx0", "banco ve por más", "banco ve por mas", "bx+"]),
    ("sabadell", ["banco sabadell,s.a"]),
    ("inbursa", ["cliente inbursa:"]),
    # HSBC PDFs have garbled CID-encoded text
    ("hsbc", ["(cid:228)"]),
    ("scotiabank", ["estadodecuenta cu"]),
    ("banorte", ["enlace negocios", "banco mercantil del norte"]),
    ("bbva", ["cash management m.n", "bbva mexico, s.a", "www.bbva.mx", "bbva adelante"]),
    ("banamex", ["cuenta de cheques moneda nacional", "citibanamex"]),
    ("santander", ["bancosantanderm", "banco santander (méxico)", "banco santander (mexico)", "santander pyme", "banco santander"]),
]


def detect_bank_from_text(text: str) -> str | None:
    """
    Detect bank from structural text patterns unique to each bank's format.
    """
    header = text[:8000].lower()

    # Phase 1: High-precision structural patterns
    for bank_key, patterns in TEXT_FALLBACK_PATTERNS:
        for pattern in patterns:
            if pattern in header:
                return bank_key

    # Phase 2: Simple fallback keywords in header
    fallback_keywords = [
        ("bbva", ["bbva", "bancomer"]),
        ("hsbc", ["hsbc"]),
        ("santander", ["santander"]),
        ("banorte", ["banorte"]),
        ("scotiabank", ["scotiabank"]),
        ("banamex", ["banamex", "citibanamex"]),
        ("inbursa", ["inbursa"]),
        ("sabadell", ["sabadell"]),
        ("bxplus", ["bx+", "bxplus", "ve por mas", "ve por más"]),
    ]
    for bank_key, keywords in fallback_keywords:
        for keyword in keywords:
            if keyword in header:
                return bank_key

    return None


def detect_bank(pdf_path: str | Path = None, text: str = "") -> str | None:
    """
    Main detection function. Tries filename heuristics first, then text patterns.
    Gemini Vision is NOT used.

    Args:
        pdf_path: Path to the PDF file (for filename heuristics)
        text: Extracted text from the PDF

    Returns:
        Bank key (e.g. "hsbc", "bbva") or None
    """
    # 1. Try filename heuristics (fast, free, local)
    if pdf_path:
        filename = Path(pdf_path).name.lower()
        for bank_key in VALID_BANKS:
            if bank_key == "bxplus":
                if "bxplus" in filename or "bx+" in filename or "ve por mas" in filename or "ve por más" in filename:
                    logger.info(f"Filename heuristic detected bank: bxplus")
                    return "bxplus"
            elif bank_key in filename:
                logger.info(f"Filename heuristic detected bank: {bank_key}")
                return bank_key

    # 2. Text-based detection
    if text:
        bank = detect_bank_from_text(text)
        if bank:
            logger.info(f"Text detection detected bank: {bank}")
            return bank

    logger.warning("Could not detect bank from filename or text")
    return None

def _render_first_page_as_image(pdf_bytes: bytes) -> bytes:
    """
    Render the first page of a PDF as a PNG image using PyMuPDF from memory bytes.
    """
    doc = fitz.open("pdf", pdf_bytes)
    page = doc[0]
    pix = page.get_pixmap(dpi=200)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes

def detect_bank_with_gemini(pdf_bytes: bytes) -> str | None:
    """
    Send the first page of the PDF as an image to Gemini Vision
    and ask it to identify the bank from the logo/header.
    """
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY configured, skipping vision detection")
        return None
    
    try:
        png_bytes = _render_first_page_as_image(pdf_bytes)
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = (
            "Mira esta imagen de un estado de cuenta bancario mexicano. "
            "Identifica el banco que EMITIÓ este documento basándote en el LOGO o encabezado principal del banco. "
            "IGNORA cualquier nombre de banco que aparezca en los movimientos o transacciones. "
            "Solo me interesa el banco que generó este estado de cuenta.\n\n"
            f"Los bancos posibles son ÚNICAMENTE estos: {', '.join(VALID_BANKS)}\n\n"
            "Responde SOLAMENTE con el nombre del banco en minúsculas, sin explicación. "
            "Ejemplo de respuesta válida: bbva"
        )
        
        image_part = {"mime_type": "image/png", "data": png_bytes}
        response = model.generate_content([prompt, image_part])
        answer = response.text.strip().lower()
        
        for bank in VALID_BANKS:
            if bank in answer:
                logger.info(f"Gemini Vision detected bank: {bank}")
                return bank
        
        logger.warning(f"Gemini returned unrecognized bank: '{answer}'")
        return None
        
    except Exception as e:
        logger.error(f"Gemini Vision detection failed: {e}")
        return None

