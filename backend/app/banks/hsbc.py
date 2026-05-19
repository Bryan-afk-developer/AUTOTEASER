"""
AutoTeaser - HSBC Bank Statement Parser
Uses Gemini Vision as OCR because HSBC PDFs have copy-protection
(text is encoded as CID glyphs, making pdfplumber extraction useless).

Strategy:
1. Render each relevant page as an image via PyMuPDF
2. Send the image(s) to Gemini with a strict prompt to extract ONLY:
   - Account number
   - Month and year
   - Total deposits
   - Average balance (Saldo Promedio)
3. Parse Gemini's structured text response with regex (NO JSON to avoid truncation)
"""
import re
import logging
from pathlib import Path

import fitz  # PyMuPDF
import google.generativeai as genai

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# ── Gemini OCR prompt ──
# Strict instructions to prevent hallucination
OCR_PROMPT = """Analiza esta imagen de un estado de cuenta de HSBC México.
Extrae SOLAMENTE estos 4 datos. Si no encuentras alguno, pon "NO ENCONTRADO".

Responde EXACTAMENTE en este formato (una línea por dato):
CUENTA: [número de cuenta, solo dígitos, ejemplo: 4071361352]
PERIODO: [mes en español y año, ejemplo: septiembre 2025]
DEPOSITOS: [monto total de depósitos, ejemplo: 1234567.89]
SALDO_PROMEDIO: [saldo promedio en el mes, ejemplo: 987654.32]

REGLAS:
- Para DEPOSITOS busca "Total de depósitos" o "Depósitos" en el resumen del periodo
- Para SALDO_PROMEDIO busca "SALDO PROMEDIO EN EL MES" o "Saldo Promedio" en el resumen
- Los montos deben ser números sin signo de pesos ($) y sin comas
- El mes debe estar en español completo (enero, febrero, etc.)
"""


def _render_pages_as_images(pdf_path: str | Path, page_indices: list[int] = None) -> list[bytes]:
    """Render specified PDF pages as PNG images."""
    doc = fitz.open(str(pdf_path))
    if page_indices is None:
        page_indices = [0]  # Default: first page only
    
    images = []
    for idx in page_indices:
        if idx < len(doc):
            page = doc[idx]
            pix = page.get_pixmap(dpi=200)
            images.append(pix.tobytes("png"))
    doc.close()
    return images


def _extract_with_gemini(pdf_path: str | Path) -> dict | None:
    """
    Use Gemini Vision to OCR the HSBC statement and extract financial data.
    Tries multiple models in case of quota exhaustion.
    Returns a dict with raw extracted values or None on failure.
    """
    if not GEMINI_API_KEY:
        logger.error("HSBC parser requires GEMINI_API_KEY but none is configured")
        return None

    # Model fallback chain: try each until one works
    MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

    try:
        genai.configure(api_key=GEMINI_API_KEY)

        # Render first 2 pages (summary is usually on page 1)
        images = _render_pages_as_images(pdf_path, [0, 1])
        if not images:
            logger.error("Could not render PDF pages")
            return None

        # Build multimodal content
        content_parts = [OCR_PROMPT]
        for img_bytes in images:
            content_parts.append({
                "mime_type": "image/png",
                "data": img_bytes,
            })

        # Try each model
        for model_name in MODELS:
            try:
                logger.info(f"HSBC: trying model {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(content_parts)
                raw_text = response.text.strip()
                logger.info(f"HSBC Gemini OCR response ({model_name}):\n{raw_text}")
                return _parse_gemini_response(raw_text)
            except Exception as model_err:
                err_str = str(model_err).lower()
                if "quota" in err_str or "resource_exhausted" in err_str or "429" in err_str:
                    logger.warning(f"HSBC: {model_name} quota exhausted, trying next model...")
                    continue
                else:
                    logger.error(f"HSBC: {model_name} failed with non-quota error: {model_err}")
                    raise

        logger.error("HSBC: all Gemini models exhausted quota")
        return None

    except Exception as e:
        logger.error(f"HSBC Gemini OCR failed: {e}", exc_info=True)
        return None


def _parse_gemini_response(text: str) -> dict:
    """Parse Gemini's structured text response into a dict."""
    result = {}

    # CUENTA: 4071361352
    m = re.search(r'CUENTA:\s*(\d+)', text)
    if m:
        result["account_num"] = m.group(1)

    # PERIODO: septiembre 2025
    m = re.search(r'PERIODO:\s*(\w+)\s+(\d{4})', text, re.IGNORECASE)
    if m:
        result["month_raw"] = m.group(1).lower()
        result["year"] = m.group(2)

    # DEPOSITOS: 1234567.89
    m = re.search(r'DEPOSITOS:\s*([\d.]+)', text)
    if m:
        result["deposits"] = float(m.group(1))

    # SALDO_PROMEDIO: 987654.32
    m = re.search(r'SALDO_PROMEDIO:\s*([\d.]+)', text)
    if m:
        result["average_balance"] = float(m.group(1))

    return result


def parse(text: str, pages: list[str], pdf_path: str | Path = None) -> dict:
    """
    Parse an HSBC bank statement using Gemini Vision OCR.
    
    Args:
        text: Full extracted text from the PDF (usually garbled CID codes for HSBC)
        pages: List of text per page (usually garbled)
        pdf_path: Path to the original PDF file (REQUIRED for HSBC to render images)
    
    Returns:
        dict with account_name, month, year, deposits, average_balance
    """
    result = {
        "account_name": "",
        "month": "",
        "year": "",
        "deposits": 0.0,
        "average_balance": 0.0,
    }

    meses_map = {
        'enero': 'ene', 'febrero': 'feb', 'marzo': 'mar', 'abril': 'abr',
        'mayo': 'may', 'junio': 'jun', 'julio': 'jul', 'agosto': 'ago',
        'septiembre': 'sep', 'octubre': 'oct', 'noviembre': 'nov', 'diciembre': 'dic',
    }

    if not pdf_path:
        logger.error("HSBC parser requires pdf_path to render images for OCR")
        return result

    # Call Gemini OCR
    ocr_data = _extract_with_gemini(pdf_path)
    if not ocr_data:
        logger.warning("HSBC: Gemini OCR returned no data")
        return result

    # Map extracted data
    if "account_num" in ocr_data:
        result["account_name"] = f"hsbc{ocr_data['account_num'][-4:]}"

    if "month_raw" in ocr_data:
        result["month"] = meses_map.get(ocr_data["month_raw"], ocr_data["month_raw"][:3])

    if "year" in ocr_data:
        result["year"] = ocr_data["year"]

    if "deposits" in ocr_data:
        result["deposits"] = ocr_data["deposits"]

    if "average_balance" in ocr_data:
        result["average_balance"] = ocr_data["average_balance"]

    return result
