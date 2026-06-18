import logging
import fitz  # PyMuPDF
import pdfplumber
import io
import re
from pathlib import Path
from google.cloud import documentai
from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def extract_tables_from_pages(pdf_path: str | Path, target_pages: list[int], page_layouts: dict = None) -> dict:
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

def _extract_with_document_ai(doc: fitz.Document, page_num: int, layout: dict = None) -> list:
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("DocAI variables not set. Cannot process scanned page.")
        return []

    page = doc[page_num]
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)
    
    page_width = page.rect.width
    page_height = page.rect.height
    
    # Process the FULL PAGE to preserve Document AI context and avoid hallucinations.
    # Limit max dimension to 4000px to avoid 400 errors and speed up processing.
    scale = 300 / 72
    if max(page_width, page_height) * scale > 4000:
        scale = 4000 / max(page_width, page_height)
        
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    img_bytes = pix.tobytes("png")
    
    req = documentai.ProcessRequest(name=name, raw_document=documentai.RawDocument(content=img_bytes, mime_type="image/png"))
    tables = []
    
    try:
        res = client.process_document(request=req)
        
        # Extract all tokens from the full page
        all_tokens = []
        for p in res.document.pages:
            for token in p.tokens:
                text = "".join([res.document.text[int(s.start_index) if s.start_index else 0:int(s.end_index)] for s in token.layout.text_anchor.text_segments]).strip()
                bbox = None
                vertices = token.layout.bounding_poly.normalized_vertices
                if vertices and len(vertices) >= 4 and text:
                    xs = [v.x for v in vertices]
                    ys = [v.y for v in vertices]
                    x0 = min(xs) * page_width
                    y0 = min(ys) * page_height
                    x1 = max(xs) * page_width
                    y1 = max(ys) * page_height
                    bbox = [float(x0), float(y0), float(x1), float(y1)]
                    all_tokens.append({"text": text, "bbox": bbox})
                    
        # Filter tokens by layout regions
        if layout and layout.get("type") == "two_column" and len(layout.get("regions", [])) >= 2:
            regions = sorted(layout["regions"], key=lambda r: r["x"])
            r1 = regions[0]
            r2 = regions[1]
            
            def is_inside(token_bbox, region):
                cx = (token_bbox[0] + token_bbox[2]) / 2 / page_width
                cy = (token_bbox[1] + token_bbox[3]) / 2 / page_height
                return (region["x"] <= cx <= region["x"] + region["w"]) and (region["y"] <= cy <= region["y"] + region["h"])
                
            left_tokens = [t for t in all_tokens if is_inside(t["bbox"], r1)]
            right_tokens = [t for t in all_tokens if is_inside(t["bbox"], r2)]
            
            t1 = _build_table_from_lines(left_tokens)
            if t1: tables.append(t1)
            t2 = _build_table_from_lines(right_tokens)
            if t2: tables.append(t2)
        else:
            t = _build_table_from_lines(all_tokens)
            if t: tables.append(t)
            
    except Exception as e:
        logger.error(f"DocAI Error on page {page_num}: {e}")
        
    return tables

def _build_table_from_lines(lines_list):
    if not lines_list:
        return []
        
    lines_list.sort(key=lambda l: l['bbox'][1])
    
    rows = []
    current_row = []
    for item in lines_list:
        if not current_row:
            current_row.append(item)
        else:
            y0_current = min(c['bbox'][1] for c in current_row)
            y1_current = max(c['bbox'][3] for c in current_row)
            y0_item = item['bbox'][1]
            y1_item = item['bbox'][3]
            
            overlap = max(0, min(y1_current, y1_item) - max(y0_current, y0_item))
            h_item = y1_item - y0_item
            h_current = y1_current - y0_current
            
            if overlap > 0 and overlap > min(h_item, h_current) * 0.3:
                current_row.append(item)
            else:
                current_row.sort(key=lambda c: c['bbox'][0])
                rows.append(current_row)
                current_row = [item]
                
    if current_row:
        current_row.sort(key=lambda c: c['bbox'][0])
        rows.append(current_row)
        
    return rows
