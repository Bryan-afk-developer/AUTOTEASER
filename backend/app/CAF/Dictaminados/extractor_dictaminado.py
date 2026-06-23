import logging
import re
from pathlib import Path
import fitz

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR
from google.cloud import documentai

logger = logging.getLogger(__name__)

# Regex para detectar encabezados de nota: "NOTA 5", "NOTA 5.-", "NOTA 5-", etc.
_NOTA_HEADER_RE = re.compile(r'^NOTA\s*(\d+)\b', re.IGNORECASE)


def extract_dictaminado(pdf_path, target_pages: list, page_layouts: dict = None) -> dict:
    """
    Extracción especializada para Estados Financieros Dictaminados.
    Usa Document AI para extraer los tokens y los agrupa en filas horizontales.
    Soporta el layout 'notas_dictaminado' para extraer tablas de notas automáticamente.
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

            req = documentai.ProcessRequest(
                name=name,
                raw_document=documentai.RawDocument(content=img_bytes, mime_type="image/png")
            )
            res = client.process_document(request=req)

            all_tokens = []
            for p in res.document.pages:
                for token in p.tokens:
                    text = "".join([
                        res.document.text[int(s.start_index) if s.start_index else 0:int(s.end_index)]
                        for s in token.layout.text_anchor.text_segments
                    ]).strip()
                    vertices = token.layout.bounding_poly.normalized_vertices
                    if vertices and len(vertices) >= 4 and text:
                        xs = [v.x for v in vertices]
                        ys = [v.y for v in vertices]
                        bbox = [
                            float(min(xs) * page_width),
                            float(min(ys) * page_height),
                            float(max(xs) * page_width),
                            float(max(ys) * page_height),
                        ]
                        all_tokens.append({"text": text, "bbox": bbox})

            # Determine layout type for this page
            layout_val = None
            if page_layouts:
                layout_val = page_layouts.get(str(p_num))

            layout_type = "dictaminado"
            regions = None
            if isinstance(layout_val, dict):
                layout_type = layout_val.get("type", "dictaminado")
                regions = layout_val.get("regions")
            elif isinstance(layout_val, str):
                layout_type = layout_val

            # Filter tokens by regions if provided
            if regions:
                def is_inside(token_bbox, r):
                    cx = (token_bbox[0] + token_bbox[2]) / 2 / page_width
                    cy = (token_bbox[1] + token_bbox[3]) / 2 / page_height
                    return (r["x"] <= cx <= r["x"] + r["w"]) and (r["y"] <= cy <= r["y"] + r["h"])
                filtered_tokens = [t for t in all_tokens if any(is_inside(t["bbox"], r) for r in regions)]
            else:
                filtered_tokens = all_tokens

            # Build rows from tokens
            all_rows = _build_table_from_lines(filtered_tokens)

            if layout_type == "notas_dictaminado":
                # Special mode: auto-detect "NOTA X" headers and tag rows below them
                tables = _extract_nota_tables(all_rows, page_width)
            else:
                tables = [all_rows] if all_rows else []

            results.append({
                "page_num": p_num,
                "method": "document_ai_dictaminado",
                "layout_type": layout_type,
                "tables": tables,
                "page_width": page_width,
                "page_height": page_height,
            })

        except Exception as e:
            logger.error(f"Error processing page {p_num} for dictaminado: {e}")

    doc.close()

    return {
        "pages": results,
        "year": "Desconocido",
        "doc_type": "dictaminado",
    }


def _extract_nota_tables(all_rows: list, page_width: float) -> list:
    """
    Dado un conjunto de filas de tokens, detecta los encabezados de nota
    (ej. 'NOTA 5.- CUENTAS POR COBRAR') y marca las filas que están en tablas
    debajo de ellos con un campo especial 'nota_header'.

    Retorna una lista de tablas. Cada tabla es una lista de filas donde la
    primera fila puede tener el campo is_nota_header=True.
    """
    current_nota_label = None
    current_nota_rows = []
    result_tables = []

    for row in all_rows:
        if not row:
            continue

        full_row_text = " ".join(t.get("text", "") for t in row)
        nota_match = _NOTA_HEADER_RE.match(full_row_text.strip())

        if nota_match:
            # Save previous nota section
            if current_nota_label and current_nota_rows:
                result_tables.append(_pack_nota_table(current_nota_label, current_nota_rows))
            nota_title = full_row_text.strip()
            current_nota_label = nota_title
            current_nota_rows = []
        elif current_nota_label:
            # Only accept rows that look like table data:
            # 1. Must contain at least ONE real financial amount (>=4 digits or has comma separators)
            # 2. Must NOT be a long prose paragraph (if the row has >8 non-numeric tokens, skip it)
            financial_amounts = [t for t in row if _is_financial_amount(t.get("text", ""))]
            
            # Count non-numeric tokens (words)
            word_tokens = [t for t in row if not _is_numeric_token(t.get("text", "")) and len(t.get("text", "")) > 1]
            
            # A paragraph row will have many word tokens and few/no financial amounts
            is_paragraph = len(word_tokens) >= 6 and len(financial_amounts) == 0
            
            if financial_amounts and not is_paragraph:
                current_nota_rows.append(row)

    # Flush last section
    if current_nota_label and current_nota_rows:
        result_tables.append(_pack_nota_table(current_nota_label, current_nota_rows))

    # Fallback: if no notas were found, return raw rows as a single table
    if not result_tables:
        return [all_rows]

    return result_tables


def _pack_nota_table(nota_label: str, rows: list) -> list:
    """
    Crea una representación de tabla para una nota.
    La primera 'fila' es el header de la nota (is_nota_header=True).
    Las filas restantes son las filas de datos de la tabla.
    """
    # Insert a synthetic header row marking this as a nota header
    header_row = [{"text": nota_label, "bbox": None, "is_nota_header": True}]
    return [header_row] + rows


def _is_financial_amount(text: str) -> bool:
    """
    Returns True only for real financial amounts:
    - Has comma separators (e.g. 1,423,292)
    - Starts with $ sign
    - Is a large number (4+ digits, >= 1000)
    Explicitly rejects years (2020-2026) and small numbers.
    """
    t = text.strip()
    if t.startswith('$'):
        return True
    if ',' in t:
        # Could be 1,423,292 - clean and check
        cleaned = re.sub(r'[\$,\s\(\)\-]', '', t)
        if cleaned.replace('.', '', 1).isdigit() and len(cleaned.replace('.', '')) >= 4:
            return True
    # Plain number with >= 4 digits that is NOT a year
    cleaned = re.sub(r'[\$,\s\(\)\-]', '', t)
    if cleaned.replace('.', '', 1).isdigit():
        val = float(cleaned) if cleaned else 0
        # Reject years 1990-2030
        if 1990 <= val <= 2030:
            return False
        # Accept if 4+ digits (>= 1000)
        return val >= 1000
    return False


def _is_numeric_token(text: str) -> bool:
    cleaned = re.sub(r'[\$,\s\(\)\-]', '', text)
    return bool(cleaned) and cleaned.replace('.', '', 1).isdigit()


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
