import logging
import time
from pathlib import Path
import fitz
import json
import re

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR
from google.cloud import documentai

logger = logging.getLogger(__name__)

def extract_dictaminado(pdf_path: str | Path, target_pages: list[int], page_layouts: dict = None) -> dict:
    """
    Extracción especializada para Estados Financieros Dictaminados.
    Usa Document AI para extraer los tokens y los agrupa en filas horizontales.
    Retorna doc_type='dictaminado' para que el excel_builder sepa procesarlo.
    """
    logger.info(f"Extracting Dictaminado from {pdf_path} for pages {target_pages}")
    
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("DocAI variables not set. Cannot process dictaminado.")
        return {"pages": [], "year": "Desconocido", "doc_type": "dictaminado"}
        
    doc = fitz.open(pdf_path)
    
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)
    
    results = []
    
    for p_num in target_pages:
        try:
            page = doc[p_num]
            page_width = page.rect.width
            page_height = page.rect.height
            
            scale = 300 / 72
            if max(page_width, page_height) * scale > 4000:
                scale = 4000 / max(page_width, page_height)
                
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            img_bytes = pix.tobytes("png")
            
            req = documentai.ProcessRequest(name=name, raw_document=documentai.RawDocument(content=img_bytes, mime_type="image/png"))
            res = client.process_document(request=req)
            
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
            
            # Use regions if provided, otherwise use all tokens
            regions = None
            if page_layouts:
                layout = page_layouts.get(str(p_num))
                if isinstance(layout, dict) and layout.get("regions"):
                    regions = layout["regions"]
            
            if regions:
                def is_inside(token_bbox, r):
                    cx = (token_bbox[0] + token_bbox[2]) / 2 / page_width
                    cy = (token_bbox[1] + token_bbox[3]) / 2 / page_height
                    return (r["x"] <= cx <= r["x"] + r["w"]) and (r["y"] <= cy <= r["y"] + r["h"])
                
                filtered_tokens = [t for t in all_tokens if any(is_inside(t["bbox"], r) for r in regions)]
            else:
                filtered_tokens = all_tokens
                
            # Build rows from tokens
            tables = []
            table_row = _build_table_from_lines(filtered_tokens)
            if table_row:
                tables.append(table_row)
                
            results.append({
                "page_num": p_num,
                "method": "document_ai_dictaminado",
                "tables": tables,
                "page_width": page_width,
                "page_height": page_height
            })
            
        except Exception as e:
            logger.error(f"Error processing page {p_num} for dictaminado: {e}")
            
    doc.close()
    
    return {
        "pages": results, 
        "year": "Desconocido", 
        "doc_type": "dictaminado"
    }

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
            
            # Require at least 30% overlap to be on the same line
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
