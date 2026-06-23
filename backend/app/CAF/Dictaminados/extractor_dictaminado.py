import logging
import re
from pathlib import Path
import fitz

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR
from google.cloud import documentai

logger = logging.getLogger(__name__)

# Regex para detectar encabezados de nota: "NOTA 5", "NOTA 5.-", "NOTA 5-", etc.
_NOTA_HEADER_RE = re.compile(r'^NOTA\s*\d+', re.IGNORECASE)


def extract_dictaminado(pdf_path, target_pages: list, page_layouts: dict = None) -> dict:
    """
    Extracción especializada para Estados Financieros Dictaminados.
    Usa Document AI para extraer los tokens y los agrupa en filas horizontales.
    En modo notas_dictaminado usa la detección nativa de tablas de DocAI.
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

            if layout_type == "notas_dictaminado":
                # ── NOTAS MODE: use DocAI native table + block detection ──────
                tables = _extract_notas_with_native_tables(res, page_width, page_height)
            else:
                # ── STANDARD DICTAMINADO MODE: manual token grouping ──────────
                all_tokens = _extract_tokens(res, page_width, page_height)

                # Filter by regions if provided
                if regions:
                    def is_inside(token_bbox, r):
                        cx = (token_bbox[0] + token_bbox[2]) / 2 / page_width
                        cy = (token_bbox[1] + token_bbox[3]) / 2 / page_height
                        return (r["x"] <= cx <= r["x"] + r["w"]) and (r["y"] <= cy <= r["y"] + r["h"])
                    filtered_tokens = [t for t in all_tokens if any(is_inside(t["bbox"], r) for r in regions)]
                else:
                    filtered_tokens = all_tokens

                all_rows = _build_table_from_lines(filtered_tokens)
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
            logger.error(f"Error processing page {p_num} for dictaminado: {e}", exc_info=True)

    doc.close()

    return {
        "pages": results,
        "year": "Desconocido",
        "doc_type": "dictaminado",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NOTAS MODE: uses DocAI native tables
# ─────────────────────────────────────────────────────────────────────────────

def _extract_notas_with_native_tables(res, page_width: float, page_height: float) -> list:
    """
    Usa la detección nativa de tablas de Document AI y los bloques de texto
    para asociar cada tabla a su encabezado NOTA X correspondiente.

    Retorna lista de tablas (cada tabla = lista de filas).
    """
    full_text = res.document.text

    # 1. Collect all NOTA headers with their Y positions from blocks/paragraphs
    nota_headers = []  # list of (y_norm, label)
    for docai_page in res.document.pages:
        for block in docai_page.blocks:
            block_text = _layout_text(block.layout, full_text).strip()
            if _NOTA_HEADER_RE.match(block_text):
                verts = block.layout.bounding_poly.normalized_vertices
                if verts:
                    y = min(v.y for v in verts)
                    nota_headers.append((y, block_text.replace("\n", " ")))

    nota_headers.sort(key=lambda x: x[0])
    logger.info(f"Found {len(nota_headers)} NOTA headers: {[n[1] for n in nota_headers]}")

    # 2. Collect all DocAI tables with their Y positions
    docai_tables = []  # list of (y_norm, rows)
    for docai_page in res.document.pages:
        for table in docai_page.tables:
            verts = table.layout.bounding_poly.normalized_vertices
            table_y = min(v.y for v in verts) if verts else 0

            rows = []
            # Process header rows (often "Tipo de inventario | 2024 | 2023")
            for hrow in table.header_rows:
                cells = _extract_row_cells(hrow, full_text, page_width, page_height)
                if cells:
                    rows.append(cells)

            # Process body rows
            for brow in table.body_rows:
                cells = _extract_row_cells(brow, full_text, page_width, page_height)
                if cells:
                    rows.append(cells)

            if rows:
                docai_tables.append((table_y, rows))

    docai_tables.sort(key=lambda x: x[0])
    logger.info(f"Found {len(docai_tables)} DocAI tables on this page")

    if not nota_headers and not docai_tables:
        return []

    # 3. Associate each table to the nearest NOTA header ABOVE it
    result_tables = []

    for table_y, rows in docai_tables:
        # Find the last NOTA header whose Y is above this table
        matching_nota = None
        for nota_y, nota_label in nota_headers:
            if nota_y < table_y:
                matching_nota = nota_label
            else:
                break

        # Pack with the header
        if matching_nota:
            header_row = [{"text": matching_nota, "bbox": None, "is_nota_header": True}]
            result_tables.append([header_row] + rows)
        else:
            # No NOTA header found above this table, include anyway without header
            result_tables.append(rows)

    # 4. If some NOTA headers had no tables below them (e.g. NOTA 7 with just text),
    #    add them as standalone headers so they still appear in the Excel
    tables_per_nota = set()
    for table_y, rows in docai_tables:
        for nota_y, nota_label in nota_headers:
            if nota_y < table_y:
                tables_per_nota.add(nota_label)

    for nota_y, nota_label in nota_headers:
        if nota_label not in tables_per_nota:
            header_row = [{"text": nota_label, "bbox": None, "is_nota_header": True}]
            result_tables.append([header_row])

    # Sort result_tables by their first row's position (approximate by order of insertion)
    # Actually they're already in Y order since we process docai_tables in order
    return result_tables


def _extract_row_cells(row, full_text: str, page_width: float, page_height: float) -> list:
    """Extracts cells from a DocAI table row into our token format."""
    cells = []
    for cell in row.cells:
        text = _layout_text(cell.layout, full_text).strip().replace("\n", " ")
        if not text:
            continue
        verts = cell.layout.bounding_poly.normalized_vertices
        bbox = None
        if verts and len(verts) >= 4:
            xs = [v.x * page_width for v in verts]
            ys = [v.y * page_height for v in verts]
            bbox = [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]
        cells.append({"text": text, "bbox": bbox})
    return cells


def _layout_text(layout, full_text: str) -> str:
    """Extracts the text of a DocAI layout element."""
    result = ""
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index) if segment.start_index else 0
        end = int(segment.end_index)
        result += full_text[start:end]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Standard helpers (shared with other layouts)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_tokens(res, page_width: float, page_height: float) -> list:
    """Extracts all tokens from a DocAI response."""
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
    return all_tokens


def _is_numeric_token(text: str) -> bool:
    cleaned = re.sub(r'[\$,\s\(\)\-]', '', text)
    return bool(cleaned) and cleaned.replace('.', '', 1).isdigit()


def _is_financial_amount(text: str) -> bool:
    """Returns True only for real financial amounts (≥1000 or with $)."""
    t = text.strip()
    if t.startswith('$'):
        return True
    if ',' in t:
        cleaned = re.sub(r'[\$,\s\(\)\-]', '', t)
        if cleaned.replace('.', '', 1).isdigit() and len(cleaned.replace('.', '')) >= 4:
            return True
    cleaned = re.sub(r'[\$,\s\(\)\-]', '', t)
    if cleaned.replace('.', '', 1).isdigit():
        try:
            val = float(cleaned)
        except ValueError:
            return False
        if 1990 <= val <= 2030:
            return False
        return val >= 1000
    return False


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
