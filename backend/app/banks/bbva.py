"""
AutoTeaser - BBVA Bank Statement Parser
Logic specific to BBVA Mexico bank statements.

BBVA format (from example 2025.11 - BBVA 0757.pdf):
- Account in "No. de Cuenta 0169920757"
- Date in "Periodo DEL 01/11/2025 AL 30/11/2025"
- Saldo Promedio in "Saldo Promedio 2,603,512.56"
- Deposits in "Depósitos / Abonos (+) 456 76,778,579.95"
  (the number after (+) is the transaction count, the big number is the total)

Supports both native-text PDFs and scanned (image-only) PDFs via Document AI OCR.
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _ocr_first_page(pdf_path: str | Path) -> str:
    """Render page 1 as image and OCR it with Document AI Basic OCR. Returns text."""
    try:
        import fitz
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai
        from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_BASIC_OCR, GCP_PROCESSOR_ID_OCR

        processor_id = GCP_PROCESSOR_ID_BASIC_OCR or GCP_PROCESSOR_ID_OCR
        if not GCP_PROJECT_ID or not processor_id:
            logger.warning("BBVA OCR: GCP credentials not configured")
            return ""

        logger.info("BBVA: Rendering page 1 as image for OCR...")
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        pix = page.get_pixmap(dpi=200)
        png_bytes = pix.tobytes("png")
        doc.close()

        opts = ClientOptions(api_endpoint=f"{GCP_LOCATION}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, processor_id)

        raw_document = documentai.RawDocument(content=png_bytes, mime_type="image/png")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        logger.info(f"BBVA: Sending page image to Document OCR Basic (Processor: {processor_id})...")
        result = client.process_document(request=request)

        ocr_text = result.document.text or ""
        logger.info(f"BBVA: OCR extracted {len(ocr_text)} chars from page 1")
        return ocr_text

    except Exception as e:
        logger.error(f"BBVA OCR failed: {e}", exc_info=True)
        return ""


def _extract_fields(text: str) -> dict:
    """Apply regex to extract the 4 required fields from text."""
    result = {
        "account_name": "",
        "month": "",
        "year": "",
        "deposits": 0.0,
        "average_balance": 0.0,
    }

    meses_num = {
        '01': 'ene', '02': 'feb', '03': 'mar', '04': 'abr',
        '05': 'may', '06': 'jun', '07': 'jul', '08': 'ago',
        '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dic',
    }

    # ── 1. Account Name ──
    # "No. de Cuenta 0169920757"
    match_acc = re.search(r'No\.?\s*de\s*Cuenta\s+(\d{8,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"bbva{num[-4:]}"

    # ── 2. Month & Year ──
    # "Periodo DEL 01/11/2025 AL 30/11/2025"
    match_date = re.search(
        r'(?:Periodo\s+)?DEL\s+\d{1,2}/(\d{2})/(\d{4})\s+AL\s+\d{1,2}/(\d{2})/(\d{4})',
        text, re.IGNORECASE
    )
    if match_date:
        m_num = match_date.group(3)
        result["year"] = match_date.group(4)
        result["month"] = meses_num.get(m_num, m_num)
    else:
        # Fallback: "Fecha de Corte 30/11/2025"
        match_date2 = re.search(
            r'Fecha\s+de\s+Corte\s+\d{1,2}/(\d{2})/(\d{4})',
            text, re.IGNORECASE
        )
        if match_date2:
            m_num = match_date2.group(1)
            result["year"] = match_date2.group(2)
            result["month"] = meses_num.get(m_num, m_num)

    # ── 3. Average Balance (Saldo Promedio) ──
    match_bal = re.search(
        r'Saldo\s+Promedio\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "Depósitos / Abonos (+) 456 76,778,579.95"
    match_dep = re.search(
        r'Dep[oó]sitos\s*/\s*Abonos\s*\(\+\)\s*\d+\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_dep:
        match_dep = re.search(
            r'(?:Dep[oó]sitos|Abonos)\s*(?:\(\+\))?\s*\d*\s*([\d,]+\.\d{2})',
            text, re.IGNORECASE
        )
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result


def parse(text: str, pages: list[str], pdf_path: str | Path = None, **kwargs) -> dict:
    """
    Parse a BBVA bank statement.
    
    If the PDF is scanned (no native text), uses Document AI OCR on page 1.
    """
    # Try regex on native text first
    result = _extract_fields(text)

    # If critical fields are missing and we have the PDF path, try OCR
    missing_critical = not result["account_name"] or result["deposits"] == 0.0
    if missing_critical and pdf_path:
        logger.info("BBVA: Native text empty or incomplete. Trying OCR on page 1...")
        ocr_text = _ocr_first_page(pdf_path)
        if ocr_text:
            result = _extract_fields(ocr_text)

    return result
