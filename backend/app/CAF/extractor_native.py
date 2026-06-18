import fitz
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def _is_numeric(text):
    """Checa si un texto parece un número (con comas, $, negativos, paréntesis, etc.)."""
    cleaned = text.replace(",", "").replace("$", "").replace(" ", "").replace("-", "").replace(".", "").replace("(", "").replace(")", "")
    return cleaned.isdigit() and len(cleaned) > 0

def extract_native_text(pdf_path: Path | str, page_num: int) -> list:
    """
    Extrae texto de un PDF nativo usando PyMuPDF (fitz) sin depender de líneas de tabla.
    Agrupa los textos en filas de [Concepto, Monto].
    """
    extracted_tables = []
    
    try:
        doc = fitz.open(str(pdf_path))
        if page_num >= len(doc):
            return []
            
        page = doc[page_num]
        
        # Extract dictionary of blocks, lines, and spans
        # This gives us text and exact coordinates
        blocks = page.get_text("dict")["blocks"]
        
        all_lines = []
        for b in blocks:
            if b.get("type") == 0:  # Text block
                for line in b.get("lines", []):
                    # Combine all spans in a line
                    text = " ".join([s["text"] for s in line["spans"]]).strip()
                    if text:
                        bbox = line["bbox"]  # [x0, y0, x1, y1]
                        all_lines.append({
                            "text": text,
                            "bbox": bbox,
                            "y_center": (bbox[1] + bbox[3]) / 2,
                            "x_center": (bbox[0] + bbox[2]) / 2
                        })
                        
        if not all_lines:
            return []
            
        # Sort lines by vertical position (Y coordinate), with a small tolerance for same row
        all_lines.sort(key=lambda l: l["y_center"])
        
        # Group lines that belong to the same vertical row (tolerance ~5 pixels)
        rows_grouped = []
        current_row = []
        current_y = None
        
        for line in all_lines:
            if current_y is None:
                current_y = line["y_center"]
                current_row.append(line)
            else:
                if abs(line["y_center"] - current_y) < 5:
                    current_row.append(line)
                else:
                    # Sort row by horizontal position (X coordinate)
                    current_row.sort(key=lambda x: x["x_center"])
                    rows_grouped.append(current_row)
                    current_row = [line]
                    current_y = line["y_center"]
                    
        if current_row:
            current_row.sort(key=lambda x: x["x_center"])
            rows_grouped.append(current_row)
            
        # Now pair up Concepts and Amounts
        table_data = []
        for row in rows_grouped:
            # We want to form pairs of [Concept, Amount]
            # Since financial statements often have one string and one number per line:
            concept_parts = []
            amount_parts = []
            
            for item in row:
                if _is_numeric(item["text"]):
                    amount_parts.append(item)
                else:
                    concept_parts.append(item)
                    
            if concept_parts or amount_parts:
                concept_text = " ".join([c["text"] for c in concept_parts])
                # Calculate bounding box for concept
                if concept_parts:
                    cx0 = min([c["bbox"][0] for c in concept_parts])
                    cy0 = min([c["bbox"][1] for c in concept_parts])
                    cx1 = max([c["bbox"][2] for c in concept_parts])
                    cy1 = max([c["bbox"][3] for c in concept_parts])
                    concept_bbox = [cx0, cy0, cx1, cy1]
                else:
                    concept_bbox = amount_parts[0]["bbox"] if amount_parts else None

                amount_text = " ".join([a["text"] for a in amount_parts])
                if amount_parts:
                    ax0 = min([a["bbox"][0] for a in amount_parts])
                    ay0 = min([a["bbox"][1] for a in amount_parts])
                    ax1 = max([a["bbox"][2] for a in amount_parts])
                    ay1 = max([a["bbox"][3] for a in amount_parts])
                    amount_bbox = [ax0, ay0, ax1, ay1]
                else:
                    amount_bbox = concept_parts[-1]["bbox"] if concept_parts else None

                table_data.append([
                    {"text": concept_text.strip(), "bbox": concept_bbox},
                    {"text": amount_text.strip(), "bbox": amount_bbox}
                ])
                
        if table_data:
            extracted_tables.append(table_data)
            
    except Exception as e:
        logger.error(f"Error en extract_native_text: {e}")
        
    return extracted_tables
