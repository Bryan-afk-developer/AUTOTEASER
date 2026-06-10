import logging
import fitz  # PyMuPDF
import pdfplumber
import io
import re
from pathlib import Path
from google.cloud import documentai
from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def extract_tables_from_pages(pdf_path: str | Path, target_pages: list[int]) -> dict:
    """
    Extracts tables from specific pages of a PDF.
    Strategy:
    1. Check if the page has native text.
    2. If it has native text, use pdfplumber to extract tables and their bounding boxes.
    3. If it has NO native text (scanned), use Document AI Form Parser.
    Returns a unified format:
    [
        {
            "page": 1,
            "method": "pdfplumber",
            "tables": [
                [ {"text": "Activo Circulante", "bbox": [x0, y0, x1, y1]}, {"text": "1000", "bbox": [x0, y0, x1, y1]} ],
                ...
            ]
        }
    ]
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    results = []

    for p_num in target_pages:
        if p_num < 0 or p_num >= len(doc):
            continue
            
        page = doc[p_num]
        text = page.get_text("text").strip()
        
        page_result = {
            "page_num": p_num,
            "method": "unknown",
            "tables": [],
            "page_width": page.rect.width,
            "page_height": page.rect.height
        }

        if len(text) > 50:
            # Has native text -> use pdfplumber
            page_result["method"] = "pdfplumber"
            page_tables = _extract_with_pdfplumber(pdf_path, p_num)
            page_result["tables"] = page_tables
        else:
            # Scanned -> use Document AI
            page_result["method"] = "document_ai"
            page_tables = _extract_with_document_ai(doc, p_num)
            page_result["tables"] = page_tables
            
        results.append(page_result)

    doc.close()
    
    # Attempt to detect the year from all text found or from a quick scan of the first few pages
    # We open it again briefly just to scan text if needed, or use the text we already got.
    full_text = ""
    try:
        tmp_doc = fitz.open(str(pdf_path))
        for i in range(min(4, len(tmp_doc))):
            full_text += tmp_doc[i].get_text("text") + " "
        tmp_doc.close()
    except Exception:
        pass
        
    year = _detect_year(full_text)

    return {"pages": results, "year": year}

def _detect_year(text: str) -> str:
    """Detects the year in the document text, up to 2026."""
    import datetime
    current_year = 2026 # As specified by user context
    
    # Look for 4 digit numbers starting with 20
    matches = re.findall(r'\b(20[1-2][0-9])\b', text)
    if not matches:
        return "Desconocido"
        
    years = [int(y) for y in matches if int(y) <= current_year]
    if not years:
        return "Desconocido"
        
    # Return the most frequent or simply the highest year
    # Usually the highest year mentioned is the reporting year
    return str(max(years))

def _extract_with_pdfplumber(pdf_path: Path, page_num: int) -> list:
    """Extract tables and cell bounding boxes using pdfplumber."""
    extracted_tables = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        if page_num >= len(pdf.pages):
            return []
        page = pdf.pages[page_num]
        
        # Get raw tables with cell bounding boxes
        tables = page.find_tables()
        for table in tables:
            cells = table.cells
            table_data = []
            for row in table.rows:
                row_data = []
                for cell in row:
                    if cell is None:
                        row_data.append({"text": "", "bbox": None})
                        continue
                        
                    x0, top, x1, bottom = cell
                    # Crop the page to the cell's bbox to extract the exact text
                    cell_crop = page.within_bbox((x0, top, x1, bottom))
                    text = cell_crop.extract_text(layout=True)
                    if text:
                        text = text.strip()
                    else:
                        text = ""
                    
                    row_data.append({
                        "text": text,
                        "bbox": [float(x0), float(top), float(x1), float(bottom)]
                    })
                table_data.append(row_data)
            extracted_tables.append(table_data)
            
    return extracted_tables

def _extract_with_document_ai(doc: fitz.Document, page_num: int) -> list:
    """Extract tables using Google Document AI."""
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("DocAI variables not set. Cannot process scanned page.")
        return []

    # Render page to image
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
    img_bytes = pix.tobytes("png")

    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)

    raw_document = documentai.RawDocument(content=img_bytes, mime_type="image/png")
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    
    try:
        result = client.process_document(request=request)
        document = result.document
    except Exception as e:
        logger.error(f"DocAI Error on page {page_num}: {e}")
        return []

    extracted_tables = []
    page_width = page.rect.width
    page_height = page.rect.height

    for doc_page in document.pages:
        for table in doc_page.tables:
            table_data = []
            all_rows = list(table.header_rows) + list(table.body_rows)
            for row in all_rows:
                row_data = []
                for cell in row.cells:
                    # Extract text
                    cell_text = ""
                    for segment in cell.layout.text_anchor.text_segments:
                        start = int(segment.start_index) if segment.start_index else 0
                        end = int(segment.end_index)
                        cell_text += document.text[start:end]
                    cell_text = cell_text.strip()
                    
                    # Extract bounding box and convert from normalized to absolute coordinates
                    bbox = None
                    vertices = cell.layout.bounding_poly.normalized_vertices
                    if vertices and len(vertices) >= 4:
                        xs = [v.x for v in vertices]
                        ys = [v.y for v in vertices]
                        x0 = min(xs) * page_width
                        y0 = min(ys) * page_height
                        x1 = max(xs) * page_width
                        y1 = max(ys) * page_height
                        bbox = [float(x0), float(y0), float(x1), float(y1)]
                        
                    row_data.append({
                        "text": cell_text,
                        "bbox": bbox
                    })
                table_data.append(row_data)
            extracted_tables.append(table_data)

    return extracted_tables
