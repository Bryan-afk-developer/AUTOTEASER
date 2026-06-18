import logging
import fitz  # PyMuPDF
import pdfplumber
import io
import re
from pathlib import Path
from google.cloud import documentai
from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def extract_tables_from_pages(pdf_path: str | Path, target_pages: list[int], page_layouts: dict = None, use_ocr: bool = True) -> dict:
    """
    Extracts tables from specific pages of a PDF.
    Strategy:
    1. Check if the page has native text.
    2. If it has native text and use_ocr is False, use pdfplumber to extract tables and their bounding boxes.
    3. If it has NO native text (scanned) or use_ocr is True, use Document AI Form Parser.
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

        # Extraer configuración de layout de la petición
        layout_config = page_layouts.get(str(p_num), "single_column") if page_layouts else "single_column"
        layout_type = layout_config["type"] if isinstance(layout_config, dict) else layout_config
        regions = layout_config["regions"] if isinstance(layout_config, dict) else None

        if not use_ocr and len(text) > 50:
            # Has native text -> use local fast extraction
            page_result["method"] = "native_text"
            from app.CAF.extractor_native import extract_native_text
            page_tables = extract_native_text(pdf_path, p_num)
            page_result["tables"] = page_tables
        else:
            # Scanned or explicitly requested OCR -> use Document AI
            page_result["method"] = "document_ai"
            page_tables = _extract_with_document_ai(doc, p_num, page_layouts.get(str(p_num)) if page_layouts else None)
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



def _extract_with_document_ai(doc: fitz.Document, page_num: int, layout: dict = None) -> list:
    """Extract tables using Google Document AI Form Parser."""
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("DocAI variables not set. Cannot process scanned page.")
        return []

    page = doc[page_num]
    page_width = page.rect.width
    page_height = page.rect.height
    
    scale = 300 / 72
    if max(page_width, page_height) * scale > 4000:
        scale = 4000 / max(page_width, page_height)
        
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    img_bytes = pix.tobytes("png")
    
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)
    
    req = documentai.ProcessRequest(name=name, raw_document=documentai.RawDocument(content=img_bytes, mime_type="image/png"))
    extracted_tables = []
    
    try:
        res = client.process_document(request=req)
        document = res.document
    except Exception as e:
        logger.error(f"DocAI Error on page {page_num}: {e}")
        return []

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
                    
                    # Extract bounding box
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
