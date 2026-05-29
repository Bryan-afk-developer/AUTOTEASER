"""
AutoTeaser - HSBC Bank Statement Parser
Strictly uses Regex on native text ($0), or Document OCR Basic ($0.0015) for locked PDFs.
No Gemini. No Form Parsers.
"""
import re
import logging
from pathlib import Path
import fitz

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_BASIC_OCR, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

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


def _extract_with_document_ocr_basic(pdf_path: str | Path):
    """
    Renders page 1 as an image and uses the cheap Document OCR Basic.
    Returns the document object to access layout (Y coordinates).
    """
    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai

        processor_id = GCP_PROCESSOR_ID_BASIC_OCR or GCP_PROCESSOR_ID_OCR
        if not GCP_PROJECT_ID or not processor_id:
            logger.warning("HSBC: GCP credentials or processor ID not configured for Basic OCR")
            return None

        logger.info("HSBC: Rendering page 1 as image for Basic OCR...")
        images = _render_pages_as_images(pdf_path, [0])
        if not images:
            logger.error("HSBC: Could not render PDF page as image")
            return None

        opts = ClientOptions(api_endpoint=f"{GCP_LOCATION}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, processor_id)

        raw_document = documentai.RawDocument(content=images[0], mime_type="image/png")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        logger.info(f"HSBC: Sending page image to Document OCR Basic (Processor: {processor_id})...")
        result = client.process_document(request=request)
        
        return result.document

    except Exception as e:
        logger.error(f"HSBC Document OCR Basic failed: {e}", exc_info=True)
        return None


def _apply_ocr_layout_extraction(document) -> dict:
    """Uses Y-coordinates from Document AI Basic OCR to extract table values."""
    result = {}
    if not document:
        return result

    # 1. Extract raw text for non-table fields
    text = document.text or ""
    
    # --- CUENTA ---
    m = re.search(r'(?:cuenta|número de cuenta)[^\d]*(\d{10})', text, re.IGNORECASE)
    if m:
        result["account_num"] = m.group(1)

    # --- PERIODO ---
    m = re.search(r'(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})', text)
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
        m = re.search(r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(?:de\s+)?(\d{4})', text, re.IGNORECASE)
        if m:
            result["month_raw"] = m.group(1).lower()
            result["year"] = m.group(2)

    # 2. Use Y-coordinates to extract table fields (Depósitos, Saldo Promedio)
    lines_data = []
    for page in document.pages:
        for line in getattr(page, "lines", []):
            if not getattr(line, "layout", None) or not getattr(line.layout, "text_anchor", None):
                continue
            segments = line.layout.text_anchor.text_segments
            line_text = ""
            for seg in segments:
                line_text += document.text[int(seg.start_index):int(seg.end_index)]
            
            y_coords = [v.y for v in line.layout.bounding_poly.normalized_vertices]
            y_center = sum(y_coords) / len(y_coords) if y_coords else 0
            lines_data.append({"y": y_center, "text": line_text.strip()})

    # Find deposits
    for item in lines_data:
        text_lower = item["text"].lower()
        if "depósitos" in text_lower or "depositos" in text_lower:
            target_y = item["y"]
            # Look for values in the same row (Y coordinate within 0.005)
            candidates = [x for x in lines_data if abs(x["y"] - target_y) < 0.005 and "$" in x["text"]]
            if candidates:
                val_str = candidates[-1]["text"]  # The value is usually the rightmost column
                m = re.search(r'([\d,]+\.\d{2})', val_str)
                if m:
                    result["deposits"] = float(m.group(1).replace(',', ''))
                    break

    # Find average balance
    for item in lines_data:
        text_lower = item["text"].lower()
        if "saldo promedio en el mes" in text_lower or "saldo promedio en mes" in text_lower:
            target_y = item["y"]
            candidates = [x for x in lines_data if abs(x["y"] - target_y) < 0.005 and "$" in x["text"]]
            if candidates:
                val_str = candidates[-1]["text"]
                m = re.search(r'([\d,]+\.\d{2})', val_str)
                if m:
                    result["average_balance"] = float(m.group(1).replace(',', ''))
                    break
        elif "saldo promedio" in text_lower and "average_balance" not in result:
            target_y = item["y"]
            candidates = [x for x in lines_data if abs(x["y"] - target_y) < 0.005 and "$" in x["text"]]
            if candidates:
                val_str = candidates[-1]["text"]
                m = re.search(r'([\d,]+\.\d{2})', val_str)
                if m:
                    result["average_balance"] = float(m.group(1).replace(',', ''))

    return result


def _apply_regex_extraction(text: str) -> dict:
    """Applies naive strict regular expressions to extract the 4 required points (used for native text only)."""
    result = {}
    if not text.strip():
        return result

    # --- CUENTA ---
    m = re.search(r'(?:cuenta|número de cuenta)[^\d]*(\d{10})', text, re.IGNORECASE)
    if m:
        result["account_num"] = m.group(1)

    # --- PERIODO ---
    m = re.search(r'(\d{2}/\d{2}/\d{4})\s+al\s+(\d{2}/\d{2}/\d{4})', text)
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
        m = re.search(r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*(?:de\s+)?(\d{4})', text, re.IGNORECASE)
        if m:
            result["month_raw"] = m.group(1).lower()
            result["year"] = m.group(2)

    # --- DEPOSITOS ---
    m = re.search(r'(?:total de depósitos|depósitos|depositos)[^\d]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if m:
        result["deposits"] = float(m.group(1).replace(',', ''))

    # --- SALDO PROMEDIO ---
    m = re.search(r'saldo promedio en (?:el\s+)?mes[^\d]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if not m:
        m = re.search(r'saldo promedio[^\d]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if m:
        result["average_balance"] = float(m.group(1).replace(',', ''))

    return result


def parse(text: str, pages: list[str], pdf_path: str | Path = None, engine: str = "auto") -> dict:
    """
    Parse an HSBC bank statement using $0 Native text or cheap Basic OCR with Y-coordinate layout matching.
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

    # Step 1: Try regex on native text ($0 cost)
    extracted = _apply_regex_extraction(text)
    
    # Step 2: If native text is garbled/missing data, use Basic OCR
    missing_critical = not extracted.get("account_num") or not extracted.get("deposits")
    
    if missing_critical and pdf_path:
        logger.info("HSBC: Native text extraction failed/incomplete. Falling back to Basic OCR with layout matching...")
        ocr_document = _extract_with_document_ocr_basic(pdf_path)
        if ocr_document:
            extracted = _apply_ocr_layout_extraction(ocr_document)

    # Map extracted data
    if "account_num" in extracted:
        result["account_name"] = f"hsbc{extracted['account_num'][-4:]}"

    if "month_raw" in extracted:
        result["month"] = meses_map.get(extracted["month_raw"], extracted["month_raw"][:3])

    if "year" in extracted:
        result["year"] = extracted["year"]

    if "deposits" in extracted:
        result["deposits"] = extracted["deposits"]

    if "average_balance" in extracted:
        result["average_balance"] = extracted["average_balance"]

    return result

