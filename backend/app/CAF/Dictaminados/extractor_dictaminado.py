import logging
import re
import base64
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
    last_nota_label = None

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
                sub_tables = layout_val.get("sub_tables", [])
            elif isinstance(layout_val, str):
                layout_type = layout_val

            if layout_type == "notas_dictaminado":
                # ── NOTAS MODE: use DocAI native table + block detection ──────
                tables, last_nota_label = _extract_notas_with_native_tables(res, page_width, page_height, fitz_page=page, previous_nota_label=last_nota_label)
            elif layout_type == "notas_custom":
                # ── CUSTOM NOTAS MODE: use user-drawn sub-regions ─────────────
                tables = _extract_notas_custom(res, page_width, page_height, sub_tables)
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

def _extract_notas_with_native_tables(res, page_width: float, page_height: float, fitz_page=None, previous_nota_label=None) -> tuple:
    """
    Usa la detección nativa de tablas de Document AI y los bloques de texto
    para asociar cada tabla a su encabezado NOTA X correspondiente.

    Para notas que son solo texto (sin tabla), captura un recorte de la página
    usando fitz y lo guarda como imagen base64 para mostrarlo en el Excel.

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

    # Determine what the last nota label of this page is
    if nota_headers:
        new_last_nota_label = nota_headers[-1][1]
    else:
        new_last_nota_label = previous_nota_label

    # Inject previous nota header at the top of the page so overflowing tables associate with it
    if previous_nota_label:
        nota_headers.insert(0, (-1.0, previous_nota_label))

    # 2. Collect all DocAI tables with their Y positions
    docai_tables = []  # list of (y_norm, rows)
    for docai_page in res.document.pages:
        for table in docai_page.tables:
            verts = table.layout.bounding_poly.normalized_vertices
            table_y = min(v.y for v in verts) if verts else 0

            rows = []
            # Process body rows only
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

    # 4. Text-only notas (no table below them): capture a page screenshot of that region
    tables_per_nota = set()
    for table_y, rows in docai_tables:
        for nota_y, nota_label in nota_headers:
            if nota_y < table_y:
                tables_per_nota.add(nota_label)

    for i, (nota_y, nota_label) in enumerate(nota_headers):
        if nota_label not in tables_per_nota:
            if nota_y < 0:
                continue  # This is the injected previous_nota_label, we already screenshotted it on the previous page

            header_row = [{"text": nota_label, "bbox": None, "is_nota_header": True}]

            # Capture screenshot of the nota text region
            screenshot_b64 = None
            if fitz_page is not None:
                try:
                    # Y region: from this nota header to the next nota header (or +25% of page)
                    y_start_norm = nota_y
                    if i + 1 < len(nota_headers):
                        y_end_norm = nota_headers[i + 1][0]
                    else:
                        y_end_norm = min(nota_y + 0.30, 1.0)

                    y_start_px = max(0, y_start_norm * page_height - 4)
                    y_end_px   = min(page_height, y_end_norm * page_height + 4)

                    clip = fitz.Rect(0, y_start_px, page_width, y_end_px)
                    pix = fitz_page.get_pixmap(clip=clip, dpi=150)
                    screenshot_b64 = base64.b64encode(pix.tobytes("png")).decode()
                    logger.info(f"Captured screenshot for text-only {nota_label}: y={y_start_norm:.2f}→{y_end_norm:.2f}")
                except Exception as e:
                    logger.warning(f"Could not capture screenshot for {nota_label}: {e}")

            # Build the table: just header + one image row
            if screenshot_b64:
                image_row = [{"text": "", "bbox": None, "is_nota_image": True, "image_b64": screenshot_b64}]
                result_tables.append([header_row, image_row])
            else:
                result_tables.append([header_row])

    return result_tables, new_last_nota_label


def _extract_notas_custom(res, page_width: float, page_height: float, sub_tables: list) -> list:
    """
    Extrae tablas basadas en múltiples regiones (Concepto, Val1, Val2) dibujadas por el usuario.
    """
    all_tokens = _extract_tokens(res, page_width, page_height)
    
    def is_inside(bbox, r):
        if not r: return False
        cx = (bbox[0] + bbox[2]) / 2 / page_width
        cy = (bbox[1] + bbox[3]) / 2 / page_height
        return (r["x"] <= cx <= r["x"] + r["w"]) and (r["y"] <= cy <= r["y"] + r["h"])

    tables = []
    
    for st in sub_tables:
        nota_num = st.get("nota_num", "")
        cr = st.get("concept_region")
        val_regions = st.get("value_regions", [])
        
        # Fallback for old saved state
        if not val_regions:
            v1r = st.get("val1_region")
            v2r = st.get("val2_region")
            val_regions = [r for r in [v1r, v2r] if r]

        c_tokens = [t for t in all_tokens if is_inside(t["bbox"], cr)]
        v_tokens_list = [[t for t in all_tokens if is_inside(t["bbox"], vr)] for vr in val_regions]
        
        # Group concept tokens into rows by Y position
        c_rows = _build_table_from_lines(c_tokens)
        
        table_rows = []
        # Inject the nota header first
        if nota_num:
            table_rows.append([{"text": f"NOTA {nota_num}", "is_nota_header": True}])
        
        for row_tokens in c_rows:
            y0 = min(t['bbox'][1] for t in row_tokens)
            y1 = max(t['bbox'][3] for t in row_tokens)
            h = y1 - y0
            
            concept_text = " ".join(t['text'] for t in row_tokens).strip()
            
            for v_tokens in v_tokens_list:
                v_text = ""
                v_overlap = [t for t in v_tokens if max(0, min(y1, t['bbox'][3]) - max(y0, t['bbox'][1])) > min(t['bbox'][3] - t['bbox'][1], h) * 0.3]
                if v_overlap:
                    v_text = " ".join(t['text'] for t in sorted(v_overlap, key=lambda x: x['bbox'][0]))
                    
                table_rows.append([
                    {"text": concept_text},
                    {"text": v_text},
                    {"text": ""}
                ])
            
        if len(table_rows) > (1 if nota_num else 0):
            tables.append(table_rows)
            
    return tables


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
