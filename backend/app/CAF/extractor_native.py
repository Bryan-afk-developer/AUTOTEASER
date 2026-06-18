import fitz
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def _is_numeric(text):
    """Checa si un texto parece un número (con comas, $, negativos, paréntesis, etc.)."""
    cleaned = text.replace(",", "").replace("$", "").replace(" ", "").replace("-", "").replace(".", "").replace("(", "").replace(")", "")
    return cleaned.isdigit() and len(cleaned) > 0

import pdfplumber

def extract_native_text(pdf_path: Path | str, page_num: int, layout_config: dict = None) -> list:
    """
    Extrae texto de un PDF nativo usando pdfplumber.
    Restaurado para aprovechar el agrupamiento nativo de celdas (multi-line) de pdfplumber.
    """
    extracted_tables = []
    try:
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
                
    except Exception as e:
        logger.error(f"Error en extract_native_text: {e}")
        
    return extracted_tables
