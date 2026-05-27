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


def _extract_with_documentai_gcp(pdf_path: str | Path) -> dict | None:
    """
    HSBC-specific: Render page 1 as PNG image, THEN send to Document AI.
    This forces pure visual OCR, bypassing CID glyph encoding that prevents
    Document AI from reading the RESUMEN table when processing the raw PDF.
    """
    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai
        from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR
        import re

        if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
            logger.warning("HSBC: GCP credentials not configured")
            return None

        # 1. Render page 1 as PNG image (forces OCR instead of text layer parsing)
        logger.info("HSBC: Rendering page 1 as image for Document AI OCR...")
        images = _render_pages_as_images(pdf_path, [0])
        if not images:
            logger.error("HSBC: Could not render PDF page as image")
            return None

        # 2. Send IMAGE to Document AI (not the PDF)
        opts = ClientOptions(api_endpoint=f"{GCP_LOCATION}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)

        raw_document = documentai.RawDocument(content=images[0], mime_type="image/png")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        logger.info("HSBC: Sending page image to Document AI Form Parser...")
        result = client.process_document(request=request)
        document = result.document

        # 3. Build combined text from form fields AND full OCR text
        combined_text = ""

        # Extract form fields
        for page in document.pages:
            if getattr(page, "form_fields", None):
                for field in page.form_fields:
                    key = ""
                    val = ""
                    if getattr(field.field_name, "text_anchor", None):
                        for seg in field.field_name.text_anchor.text_segments:
                            key += document.text[int(seg.start_index):int(seg.end_index)]
                    if getattr(field.field_value, "text_anchor", None):
                        for seg in field.field_value.text_anchor.text_segments:
                            val += document.text[int(seg.start_index):int(seg.end_index)]
                    key = key.strip().replace('\n', ' ')
                    val = val.strip().replace('\n', ' ')
                    if key:
                        combined_text += f"{key}: {val}\n"

        # Also include full OCR text (catches table text that wasn't parsed as form fields)
        if document.text:
            combined_text += f"\n--- FULL OCR TEXT ---\n{document.text}\n"

        logger.info(f"HSBC: ===== DOCUMENT AI IMAGE OCR OUTPUT =====\n{combined_text}\n=============================================")

        # 4. Parse with regex
        result = {}

        # --- CUENTA ---
        m = re.search(r'(?:cuenta|número de cuenta)[^\d]*(\d{10})', combined_text, re.IGNORECASE)
        if m:
            result["account_num"] = m.group(1)

        # --- PERIODO ---
        # Try date format: dd/mm/yyyy al dd/mm/yyyy
        m = re.search(r'(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})', combined_text)
        if m:
            end_date = m.group(2)
            month_num = int(end_date.split('/')[1])
            year = end_date.split('/')[2]
            month_names = {
                1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
                5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
                9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
            }
            result["month_raw"] = month_names.get(month_num, '')
            result["year"] = year
        else:
            m = re.search(r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(?:de\s+)?(\d{4})', combined_text, re.IGNORECASE)
            if m:
                result["month_raw"] = m.group(1).lower()
                result["year"] = m.group(2)

        # --- DEPOSITOS ---
        m = re.search(r'(?:total de depósitos|depósitos|depositos)[^\d]*([\d,]+\.\d{2})', combined_text, re.IGNORECASE)
        if m:
            result["deposits"] = float(m.group(1).replace(',', ''))

        # --- SALDO PROMEDIO ---
        # Prioridad: "saldo promedio en el mes" > "saldo promedio" genérico
        m = re.search(r'saldo promedio en (?:el\s+)?mes[^\d]*([\d,]+\.\d{2})', combined_text, re.IGNORECASE)
        if not m:
            m = re.search(r'saldo promedio[^\d]*([\d,]+\.\d{2})', combined_text, re.IGNORECASE)
        if m:
            result["average_balance"] = float(m.group(1).replace(',', ''))

        return result

    except Exception as e:
        logger.error(f"HSBC Document AI extraction failed: {e}", exc_info=True)
        return None


def parse(text: str, pages: list[str], pdf_path: str | Path = None, engine: str = "gemini") -> dict:
    """
    Parse an HSBC bank statement using Gemini Vision OCR or GCP Document AI Form Parser.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
        pdf_path: Path to the original PDF file (REQUIRED to render images/use GCP)
        engine: "gemini" for Gemini Vision, "documentai" for Google Cloud Document AI Form Parser
    
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
        logger.error("HSBC parser requires pdf_path to run OCR/extraction")
        return result

    # Select processing engine
    if engine == "documentai":
        logger.info("HSBC: Processing using GCP Document AI engine...")
        ocr_data = _extract_with_documentai_gcp(pdf_path)
    else:
        logger.info("HSBC: Processing using Gemini Vision engine...")
        ocr_data = _extract_with_gemini(pdf_path)

    if not ocr_data:
        logger.warning(f"HSBC: Extraction using engine '{engine}' returned no data")
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
