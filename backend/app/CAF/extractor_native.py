import fitz
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def _is_numeric(text):
    """Checa si un texto parece un número (con comas, $, negativos, paréntesis, etc.)."""
    cleaned = text.replace(",", "").replace("$", "").replace(" ", "").replace("-", "").replace(".", "").replace("(", "").replace(")", "")
    return cleaned.isdigit() and len(cleaned) > 0

def extract_native_text(pdf_path: Path | str, page_num: int, layout_config: dict = None) -> list:
    """
    Extrae texto de un PDF nativo usando PyMuPDF (fitz) respetando las regiones (layout_config).
    """
    extracted_tables = []
    
    try:
        doc = fitz.open(str(pdf_path))
        if page_num >= len(doc):
            return []
            
        page = doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height
        
        blocks = page.get_text("dict")["blocks"]
        all_spans = []
        for b in blocks:
            if b.get("type") == 0:  # Text block
                for line in b.get("lines", []):
                    for span in line["spans"]:
                        text = span["text"].strip()
                        if text:
                            all_spans.append({
                                "text": text,
                                "bbox": span["bbox"]
                            })

        if not all_spans:
            return []

        def is_inside(bbox, region):
            cx = (bbox[0] + bbox[2]) / 2 / page_width
            cy = (bbox[1] + bbox[3]) / 2 / page_height
            return (region["x"] <= cx <= region["x"] + region["w"]) and (region["y"] <= cy <= region["y"] + region["h"])

        # Función auxiliar para armar tablas desde spans (similar a _build_table_from_lines)
        def build_rows_from_spans(spans_list):
            if not spans_list: return []
            spans_list.sort(key=lambda s: s["bbox"][1])
            rows = []
            current_row = []
            for item in spans_list:
                if not current_row:
                    current_row.append(item)
                else:
                    y0_current = min(c["bbox"][1] for c in current_row)
                    y1_current = max(c["bbox"][3] for c in current_row)
                    y0_item = item["bbox"][1]
                    y1_item = item["bbox"][3]
                    
                    overlap = max(0, min(y1_current, y1_item) - max(y0_current, y0_item))
                    h_item = y1_item - y0_item
                    h_current = y1_current - y0_current
                    
                    if overlap > 0 and overlap > min(h_item, h_current) * 0.3:
                        current_row.append(item)
                    else:
                        current_row.sort(key=lambda c: c["bbox"][0])
                        rows.append(current_row)
                        current_row = [item]
            if current_row:
                current_row.sort(key=lambda c: c["bbox"][0])
                rows.append(current_row)
            return rows

        layout_type = layout_config.get("type", "single_column") if isinstance(layout_config, dict) else "single_column"
        regions = layout_config.get("regions", []) if isinstance(layout_config, dict) else []

        if layout_type == "two_column" and len(regions) >= 2:
            regions = sorted(regions, key=lambda r: r["x"])
            left_spans = [s for s in all_spans if is_inside(s["bbox"], regions[0])]
            right_spans = [s for s in all_spans if is_inside(s["bbox"], regions[1])]
            
            t1 = build_rows_from_spans(left_spans)
            if t1: extracted_tables.append(t1)
            t2 = build_rows_from_spans(right_spans)
            if t2: extracted_tables.append(t2)
            
        elif layout_type == "split_column" and len(regions) >= 2:
            from app.CAF.extractor_split_column import extract_pairs_split_column
            # extract_pairs_split_column can take all_spans and do the magic
            paired_rows = extract_pairs_split_column(all_spans, regions[0], regions[1], page_width, page_height)
            if paired_rows: extracted_tables.append(paired_rows)
            
        else:
            # single_column o manual regions limitadas
            if regions:
                filtered_spans = [s for s in all_spans if any(is_inside(s["bbox"], r) for r in regions)]
            else:
                filtered_spans = all_spans
            t = build_rows_from_spans(filtered_spans)
            if t: extracted_tables.append(t)
            
    except Exception as e:
        logger.error(f"Error en extract_native_text: {e}")
        
    return extracted_tables
