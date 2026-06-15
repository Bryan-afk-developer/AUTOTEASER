import io
import json
import logging
import re
import fitz
from PIL import Image as PILImage
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path("templates/CAF - BRIGHTEC - 2026.02 - plantilla-balance (1).xlsx")
MAPA_PATH = Path("templates/mapa.json")

THIN = Border(
    top=Side("thin", "000000"), left=Side("thin", "000000"),
    right=Side("thin", "000000"), bottom=Side("thin", "000000"),
)
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")

# Secciones del Balance según fila en la plantilla
BALANCE_SECTIONS = [
    (range(9, 19),  "ACTIVO CIRCULANTE",  "1A7A4A"),
    (range(24, 32), "ACTIVO FIJO",         "2E7D32"),
    (range(37, 40), "ACTIVO DIFERIDO",     "388E3C"),
    (range(52, 58), "PASIVO CIRCULANTE",   "C62828"),
    (range(64, 66), "PASIVO LARGO PLAZO",  "E53935"),
    (range(74, 79), "CAPITAL CONTABLE",    "6A1B9A"),
]
EDO_SECTIONS = [
    (range(7, 9),   "INGRESOS",            "1A7A4A"),
    (range(8, 12),  "COSTOS Y GASTOS",     "C62828"),
    (range(15, 18), "RESULTADO FINANCIERO","1565C0"),
    (range(20, 22), "OTROS",               "6D4C41"),
    (range(24, 25), "IMPUESTOS",           "4E342E"),
    (range(29, 30), "DEPRECIACIÓN",        "37474F"),
]

def _get_section(row_num, sheet_name):
    for rng, label, color in (BALANCE_SECTIONS if sheet_name == "Balance" else EDO_SECTIONS):
        if row_num in rng:
            return label, color
    return None, None


def _is_numeric(text):
    """Checa si un texto parece un número (con comas, $, negativos, etc.)."""
    cleaned = text.replace(",", "").replace("$", "").replace(" ", "").replace("-", "").replace(".", "")
    return cleaned.isdigit() and len(cleaned) > 0


# Ruido de OCR que se debe ignorar
_OCR_NOISE = {"$", "S", "EA", "69", "SSS", "EAEAEA", "6969", "6A", "09", "th"}


def _tokenize_cells(cells):
    """Extrae tokens limpios de una lista de celdas, separando por saltos de línea."""
    tokens = []
    for c in cells:
        if not c or not str(c.get("text", "")).strip():
            continue
        lines = str(c["text"]).strip().split('\n')
        for line in lines:
            t = line.strip()
            if t:
                tokens.append(t)
    return tokens


def _pair_tokens(tokens):
    """Agrupa tokens en pares (concepto, monto) de forma lineal."""
    pairs = []
    current_concept_parts = []

    for t in tokens:
        if t in _OCR_NOISE:
            continue
        if _is_numeric(t) or t == "-":
            concepto = " ".join(current_concept_parts).strip()
            pairs.append((concepto, t))
            current_concept_parts = []
        else:
            current_concept_parts.append(t)

    leftover = " ".join(current_concept_parts).strip()
    if leftover:
        pairs.append((leftover, ""))

    if not pairs and tokens:
        pairs.append((" | ".join(tokens), ""))

    return pairs


def _extract_pairs_single_column(row):
    """Estrategia LINEAL: tokeniza toda la fila y empareja concepto→monto secuencialmente."""
    tokens = _tokenize_cells(row)
    if not tokens:
        return []
    return _pair_tokens(tokens)


def _extract_pairs_two_column(row, page_width):
    """
    Estrategia DOBLE COLUMNA: divide las celdas en mitad izquierda y mitad derecha
    usando las coordenadas X del bounding box, luego tokeniza cada mitad independientemente.
    Esto resuelve balances donde Activo está a la izquierda y Pasivo a la derecha.
    """
    midpoint = page_width / 2.0

    left_cells = []
    right_cells = []
    no_bbox_cells = []

    for c in row:
        if not c or not str(c.get("text", "")).strip():
            continue
        bbox = c.get("bbox")
        if bbox:
            # Usar el centro X de la celda para clasificarla
            center_x = (bbox[0] + bbox[2]) / 2.0
            if center_x < midpoint:
                left_cells.append(c)
            else:
                right_cells.append(c)
        else:
            no_bbox_cells.append(c)

    # Si no hay bounding boxes, caer en modo lineal
    if not left_cells and not right_cells:
        return _extract_pairs_single_column(row)

    # Si todo cayó a un solo lado, tratarlo como lineal también
    if not left_cells or not right_cells:
        all_cells = left_cells + right_cells + no_bbox_cells
        tokens = _tokenize_cells(all_cells)
        if not tokens:
            return []
        return _pair_tokens(tokens)

    # Tokenizar cada mitad por separado
    pairs = []

    left_tokens = _tokenize_cells(sorted(left_cells, key=lambda c: c.get("bbox", [0])[0]))
    if left_tokens:
        pairs.extend(_pair_tokens(left_tokens))

    right_tokens = _tokenize_cells(sorted(right_cells, key=lambda c: c.get("bbox", [0])[0]))
    if right_tokens:
        pairs.extend(_pair_tokens(right_tokens))

    return pairs


def build_caf_excel(docs_data: list) -> bytes:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Plantilla no encontrada: {TEMPLATE_PATH}")
    if not MAPA_PATH.exists():
        raise FileNotFoundError(f"Mapa no encontrado: {MAPA_PATH}")

    with open(MAPA_PATH, "r", encoding="utf-8") as f:
        mapa = json.load(f)

    wb = load_workbook(TEMPLATE_PATH)

    for doc in docs_data:
        # ── Detectar año ─────────────────────────────────────────
        year = str(doc.get("year", "")).strip()
        if not year or year == "Desconocido":
            m = re.search(r'\b(20[1-2]\d)\b', doc.get("filename", ""))
            year = m.group(1) if m else None
        if not year:
            import uuid
            year = f"Desc_{uuid.uuid4().hex[:4]}"

        sheet_name = year
        orig = sheet_name
        cnt = 1
        while sheet_name in wb.sheetnames:
            sheet_name = f"{orig}_{cnt}"
            cnt += 1

        ws = wb.create_sheet(title=sheet_name)

        # ══════════════════════════════════════════════════════════
        # HEADERS
        # ══════════════════════════════════════════════════════════
        headers = {
            "A": ("Cuenta Extraída", 28),
            "B": ("Monto Extraído", 18),
            "C": ("Página", 8),
            "D": ("Evidencia Visual", 55),
            "E": ("Input / Ajuste", 18),
        }
        for col, (title, width) in headers.items():
            cell = ws[f"{col}1"]
            cell.value = title
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN
            ws.column_dimensions[col].width = width

        # Separador + Headers del mapa estructurado (más a la derecha)
        ws.column_dimensions["F"].width = 3  # separador
        for col, (title, width) in {"G": ("Concepto", 32), "H": ("Importe (Input)", 18)}.items():
            cell = ws[f"{col}1"]
            cell.value = title
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN
            ws.column_dimensions[col].width = width

        # ══════════════════════════════════════════════════════════
        # COLUMNAS A-E: Datos extraídos del PDF (una fila por dato)
        # ══════════════════════════════════════════════════════════
        layout_type = doc.get("layout_type", "auto")
        if layout_type == "auto":
            layout_type = doc.get("extracted_data", {}).get("layout_type", "auto")

        data_row = 2
        if "extracted_data" in doc and "pages" in doc["extracted_data"]:
            for page_data in doc["extracted_data"]["pages"]:
                p_num = page_data.get("page_num", 0) + 1
                page_width = page_data.get("page_width", 600)

                for table in page_data.get("tables", []):
                    for row in table:
                        if not row:
                            continue

                        # ── Extraer la imagen de evidencia de la fila completa ──
                        evidence_b64 = None
                        for cell_data in row:
                            if cell_data and cell_data.get("evidence_b64"):
                                evidence_b64 = cell_data["evidence_b64"]
                                break

                        # ── Decidir estrategia según layout ──
                        if layout_type == "two_column":
                            pairs = _extract_pairs_two_column(row, page_width)
                        else:
                            # single_column o auto → lineal
                            pairs = _extract_pairs_single_column(row)

                        # ── Escribir cada par como fila en Excel ──
                        for concepto, monto in pairs:
                            if not concepto and not monto:
                                continue
                            if not concepto and monto:
                                concepto = "(Monto sin concepto)"

                            # Col A: Cuenta
                            a = ws[f"A{data_row}"]
                            a.value = concepto
                            a.alignment = Alignment(vertical="center", wrap_text=True)
                            a.border = THIN

                            # Col B: Monto
                            b = ws[f"B{data_row}"]
                            b.value = monto
                            b.alignment = Alignment(vertical="center", horizontal="right")
                            b.border = THIN

                            # Col C: Página
                            c = ws[f"C{data_row}"]
                            c.value = f"Pág {p_num}"
                            c.alignment = Alignment(vertical="center", horizontal="center")
                            c.border = THIN

                            # Col D: Imagen recortada
                            img_height = 30
                            if evidence_b64:
                                try:
                                    import base64
                                    img_data = base64.b64decode(evidence_b64)
                                    pil_img = PILImage.open(io.BytesIO(img_data))
                                    w, h = pil_img.size

                                    max_w = 400
                                    if w > max_w:
                                        ratio = max_w / w
                                        w, h = max_w, int(h * ratio)

                                    xl_img = OpenpyxlImage(io.BytesIO(img_data))
                                    xl_img.width = w
                                    xl_img.height = h
                                    ws.add_image(xl_img, f"D{data_row}")
                                    img_height = h * 0.75 + 5
                                except Exception as e:
                                    logger.error(f"Error insertando imagen de evidencia: {e}")

                            # Col E: Input / Ajuste
                            e = ws[f"E{data_row}"]
                            e.fill = INPUT_FILL
                            e.alignment = Alignment(horizontal="right", vertical="center")
                            e.number_format = '#,##0.00'
                            e.border = THIN

                            ws.row_dimensions[data_row].height = max(20, img_height)
                            data_row += 1

        # ══════════════════════════════════════════════════════════
        # COLUMNAS G-H: Inputs estructurados del mapa.json
        # (enlazados a la plantilla de Balance / Edo de resultados)
        # ══════════════════════════════════════════════════════════
        input_row = 2
        for tpl_sheet in ["Balance", "Edo de resultados"]:
            if tpl_sheet not in mapa or year not in mapa[tpl_sheet]:
                continue

            concepts = mapa[tpl_sheet][year]

            # Encabezado de sección principal
            hdr = ws[f"G{input_row}"]
            hdr.value = f"── {tpl_sheet.upper()} ──"
            hdr.font = Font(bold=True, color="FFFFFF", size=11)
            hdr.fill = HEADER_FILL
            hdr.alignment = Alignment(horizontal="center", vertical="center")
            hdr.border = THIN
            ws[f"H{input_row}"].fill = HEADER_FILL
            ws[f"H{input_row}"].border = THIN
            ws.merge_cells(f"G{input_row}:H{input_row}")
            input_row += 1

            current_section = None
            for concept_name, target_cell in concepts.items():
                row_match = re.search(r'\d+', target_cell)
                if not row_match:
                    continue
                tpl_row = int(row_match.group())

                sec_label, sec_color = _get_section(tpl_row, tpl_sheet)
                if sec_label and sec_label != current_section:
                    g = ws[f"G{input_row}"]
                    g.value = sec_label
                    g.font = Font(bold=True, color="FFFFFF", size=10)
                    g.fill = PatternFill("solid", fgColor=sec_color)
                    g.alignment = Alignment(horizontal="left", vertical="center")
                    g.border = THIN
                    ws[f"H{input_row}"].fill = PatternFill("solid", fgColor=sec_color)
                    ws[f"H{input_row}"].border = THIN
                    input_row += 1
                    current_section = sec_label

                # Nombre del concepto
                g = ws[f"G{input_row}"]
                g.value = concept_name.replace("_", " ").title()
                g.alignment = Alignment(horizontal="left", vertical="center", indent=1)
                g.border = THIN

                # Input amarillo
                h = ws[f"H{input_row}"]
                h.fill = INPUT_FILL
                h.alignment = Alignment(horizontal="right", vertical="center")
                h.number_format = '#,##0.00'
                h.border = THIN

                # Fórmula en la plantilla
                if tpl_sheet in wb.sheetnames and target_cell:
                    wb[tpl_sheet][target_cell] = f"='{sheet_name}'!H{input_row}"

                input_row += 1
            input_row += 1

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
