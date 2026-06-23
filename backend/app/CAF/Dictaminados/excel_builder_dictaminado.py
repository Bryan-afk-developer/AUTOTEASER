import logging
import re
import uuid
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as OpenpyxlImage
from PIL import Image as PILImage
import io
import base64

logger = logging.getLogger(__name__)

# ── Styles ────────────────────────────────────────────────────────────────────
HEADER_FONT   = Font(bold=True, color="FFFFFF")
HEADER_FILL   = PatternFill("solid", fgColor="4CAF50")
INPUT_FILL    = PatternFill("solid", fgColor="FFF9C4")
NOTA_FILL     = PatternFill("solid", fgColor="1565C0")   # azul oscuro para headers de nota
NOTA_FONT     = Font(bold=True, color="FFFFFF", size=10)
THIN = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin'),
)
_OCR_NOISE = {".", ",", "_", "|", "/", "\\", ":", ";", "I", "l"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_numeric(text: str) -> bool:
    cleaned = re.sub(r'[\$,\s\(\)]', '', str(text))
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _tokenize_cells(row) -> list:
    """Extrae tokens de las celdas de una fila, de izquierda a derecha."""
    tokens = []
    lines_per_cell = []
    for c in row:
        if not c or not c.get("text"):
            continue
        cell_lines = [line.strip() for line in str(c["text"]).strip().split('\n')]
        lines_per_cell.append(cell_lines)

    if not lines_per_cell:
        return []

    max_lines = max(len(lines) for lines in lines_per_cell)
    for i in range(max_lines):
        for cell_lines in lines_per_cell:
            if i < len(cell_lines) and cell_lines[i]:
                tokens.append(cell_lines[i])
    return tokens


def _extract_pairs_from_native_cells(row) -> list:
    """
    For rows coming from DocAI native table detection (notas_dictaminado mode):
    cells are already separated, so we directly map:
      Cell 0 = Concepto
      Cell -2 = Monto Año 1 (second to last)
      Cell -1 = Monto Año 2 (last)
    Skips header rows (where cells don't contain financial amounts).
    """
    if not row:
        return []

    # Get text values per cell
    cell_texts = [c.get("text", "").strip() for c in row if c.get("text", "").strip()]

    if len(cell_texts) < 2:
        return []

    # First cell = concepto (everything that's not numeric at the end)
    # Last two numeric-looking cells = the two year amounts
    amounts = []
    concept_parts = []
    for t in cell_texts:
        if _is_numeric(t) or t in ("-", "$-", "$ -"):
            amounts.append(t)
        else:
            concept_parts.append(t)

    concepto = " ".join(concept_parts).strip()

    if len(amounts) >= 2:
        m1 = amounts[-2]
        m2 = amounts[-1]
    elif len(amounts) == 1:
        m1 = amounts[0]
        m2 = ""
    else:
        m1 = ""
        m2 = ""

    if not concepto and not m1 and not m2:
        return []

    return [(concepto, m1, m2)]


def _extract_pairs_dictaminado(row) -> list:
    """
    Extrae pares (Concepto, Monto1, Monto2) de una fila de dictaminado.

    REGLA CLAVE: Los dictaminados tienen columnas como:
        Concepto | (Nota Ref) | Monto Año 1 | Monto Año 2
    El número de nota (ej. "9") queda en medio de los textos.
    Para no confundirlo con un monto financiero, SIEMPRE tomamos
    los ÚLTIMOS DOS números de la fila como Monto1 y Monto2.
    """
    tokens = _tokenize_cells(row)
    if not tokens:
        return []

    # Separar todos los textos y todos los numéricos
    texts = []
    all_numbers = []
    for t in tokens:
        if t in _OCR_NOISE:
            continue
        if _is_numeric(t) or t == "-":
            all_numbers.append(t)
        else:
            texts.append(t)

    # Los últimos dos son los montos financieros; cualquier número antes es referencia de nota
    if len(all_numbers) >= 2:
        m1 = all_numbers[-2]
        m2 = all_numbers[-1]
    elif len(all_numbers) == 1:
        m1 = all_numbers[-1]
        m2 = ""
    else:
        m1 = ""
        m2 = ""

    concepto = " ".join(texts).strip()

    if not concepto and not m1:
        return []

    return [(concepto, m1, m2)]


def _write_evidence_image(ws, col: str, row_num: int, ev_b64: str) -> float:
    """Inserta imagen de evidencia en la celda, retorna altura de imagen."""
    img_height = 20
    if not ev_b64:
        return img_height
    try:
        img_data = base64.b64decode(ev_b64)
        pil_img = PILImage.open(io.BytesIO(img_data))
        orig_w, orig_h = pil_img.size
        max_w, max_h = 400, 60
        ratio = min(max_w / orig_w, max_h / orig_h)
        if ratio < 1:
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            pil_img = pil_img.resize((new_w, new_h), PILImage.Resampling.LANCZOS)
        else:
            new_w, new_h = orig_w, orig_h

        tmp = io.BytesIO()
        pil_img.save(tmp, format="PNG")
        tmp.seek(0)
        xl_img = OpenpyxlImage(tmp)
        xl_img.width = new_w
        xl_img.height = new_h
        ws.add_image(xl_img, f"{col}{row_num}")
        img_height = max(img_height, new_h * 0.75 + 5)
    except Exception as e:
        logger.error(f"Error insertando imagen de evidencia: {e}")
    return img_height


def _write_nota_header(ws, row_num: int, nota_label: str):
    """Escribe el header de una nota como celda fusionada A+B con color azul."""
    a = ws[f"A{row_num}"]
    a.value = nota_label
    a.font = NOTA_FONT
    a.fill = NOTA_FILL
    a.alignment = Alignment(horizontal="left", vertical="center", wrap_text=False)
    a.border = THIN

    b = ws[f"B{row_num}"]
    b.fill = NOTA_FILL
    b.border = THIN

    ws.merge_cells(f"A{row_num}:B{row_num}")
    ws.row_dimensions[row_num].height = 18


def _write_data_row(ws, row_num: int, concept: str, monto: str, p_num: int, ev_b64):
    """Escribe una fila de datos en las columnas A-E."""
    ws[f"A{row_num}"].value = concept
    ws[f"A{row_num}"].border = THIN

    b_cell = ws[f"B{row_num}"]
    b_cell.value = monto
    b_cell.alignment = Alignment(horizontal="right")
    b_cell.border = THIN
    if monto and '(' in str(monto) and ')' in str(monto):
        b_cell.font = Font(color="FF0000")

    c_cell = ws[f"C{row_num}"]
    c_cell.value = p_num
    c_cell.alignment = Alignment(horizontal="center")
    c_cell.border = THIN

    ws[f"D{row_num}"].border = THIN
    img_height = _write_evidence_image(ws, "D", row_num, ev_b64)

    e = ws[f"E{row_num}"]
    e.fill = INPUT_FILL
    e.alignment = Alignment(horizontal="right", vertical="center")
    e.number_format = '#,##0.00'
    e.border = THIN

    ws.row_dimensions[row_num].height = max(20, img_height)


# ── Main public function ──────────────────────────────────────────────────────

def inject_dictaminado_sheets(doc, wb, mapa):
    """
    Inyecta DOS hojas en el workbook, una por cada año detectado en el dictaminado.
    Soporta tanto el modo normal como el modo notas_dictaminado.
    """
    year_str = str(doc.get("year", "")).strip()

    if "," in year_str:
        years = [y.strip() for y in year_str.split(",") if y.strip()]
    else:
        years = [year_str]

    if not years or not any(years) or years[0] == "Desconocido":
        m = re.search(r'\b(20[1-2]\d)\b', doc.get("filename", ""))
        if m:
            years = [m.group(1)]
        else:
            years = [f"Desc_{uuid.uuid4().hex[:4]}"]

    for year_idx, current_year in enumerate(years):
        sheet_name = current_year
        orig = sheet_name
        cnt = 1
        while sheet_name in wb.sheetnames:
            sheet_name = f"{orig}_{cnt}"
            cnt += 1

        ws = wb.create_sheet(title=sheet_name)

        # ── Column headers A-E + G-H ──────────────────────────────────────────
        col_headers = {
            "A": ("Cuenta Extraída", 32),
            "B": ("Monto Extraído", 18),
            "C": ("Página", 8),
            "D": ("Evidencia Visual", 55),
            "E": ("Input / Ajuste", 18),
        }
        for col, (title, width) in col_headers.items():
            cell = ws[f"{col}1"]
            cell.value = title
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN
            ws.column_dimensions[col].width = width

        ws.column_dimensions["F"].width = 3
        for col, (title, width) in {"G": ("Concepto", 32), "H": ("Importe (Input)", 18)}.items():
            cell = ws[f"{col}1"]
            cell.value = title
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN
            ws.column_dimensions[col].width = width

        # ── Write extracted data rows ─────────────────────────────────────────
        data_row = 2

        if "extracted_data" in doc and "pages" in doc["extracted_data"]:
            for page_data in doc["extracted_data"]["pages"]:
                p_num = page_data.get("page_num", 0) + 1
                layout_type = page_data.get("layout_type", "dictaminado")

                for table in page_data.get("tables", []):
                    for row in table:
                        if not row:
                            continue

                        # Check if first cell is a nota header (injected by extractor)
                        if row and row[0].get("is_nota_header"):
                            nota_label = row[0].get("text", "NOTA")
                            _write_nota_header(ws, data_row, nota_label)
                            data_row += 1
                            continue

                        # Evidence from any cell in this row
                        evidence_b64 = None
                        for cell_data in row:
                            if cell_data and cell_data.get("evidence_b64"):
                                evidence_b64 = cell_data["evidence_b64"]
                                break

                        # Extract Concept + amounts using the right strategy:
                        # - notas_dictaminado: rows come from DocAI native tables (cells already clean)
                        # - everything else: rows come from manual token grouping
                        if layout_type == "notas_dictaminado":
                            d_pairs = _extract_pairs_from_native_cells(row)
                        else:
                            d_pairs = _extract_pairs_dictaminado(row)
                            
                        for concept, m1, m2 in d_pairs:
                            monto = m1 if year_idx == 0 else m2
                            if not concept and not monto:
                                continue
                            _write_data_row(ws, data_row, concept, monto, p_num, evidence_b64)
                            data_row += 1

        # ── Structured map (G-H columns) ──────────────────────────────────────
        input_row = 2
        section_rows = {}

        for tpl_sheet in ["Balance", "Edo de resultados"]:
            if tpl_sheet not in mapa or current_year not in mapa[tpl_sheet]:
                continue

            concepts = mapa[tpl_sheet][current_year]

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

            for section, items in concepts.items():
                s_hdr = ws[f"G{input_row}"]
                s_hdr.value = section.upper()
                s_hdr.font = Font(bold=True, size=10)
                s_hdr.fill = PatternFill("solid", fgColor="E0E0E0")
                s_hdr.border = THIN
                ws[f"H{input_row}"].fill = PatternFill("solid", fgColor="E0E0E0")
                ws[f"H{input_row}"].border = THIN

                header_row_index = input_row
                input_row += 1
                first_item_index = input_row

                for item in items:
                    c_cell = ws[f"G{input_row}"]
                    c_cell.value = item
                    c_cell.border = THIN

                    val_cell = ws[f"H{input_row}"]
                    val_cell.fill = INPUT_FILL
                    val_cell.number_format = '#,##0.00'
                    val_cell.border = THIN
                    val_cell.alignment = Alignment(horizontal="right", vertical="center")
                    input_row += 1

                last_item_index = input_row - 1
                if first_item_index <= last_item_index:
                    section_rows[section.upper()] = {
                        "header_row": header_row_index,
                        "first_item": first_item_index,
                        "last_item": last_item_index,
                    }

            ws[f"G{input_row}"].border = THIN
            ws[f"H{input_row}"].border = THIN
            input_row += 1

        # ── Formulas + verification block ─────────────────────────────────────
        SUM_FONT          = Font(bold=True, color="FFFFFF", size=10)
        COMPROBACION_FILL = PatternFill("solid", fgColor="1565C0")
        COMPROBACION_FONT = Font(bold=True, color="FFFFFF", size=11)
        RESULT_FILL       = PatternFill("solid", fgColor="E8F5E9")
        RESULT_FONT       = Font(bold=True, color="1B5E20", size=10)

        for sec_name, sec_info in section_rows.items():
            h_cell = ws[f"H{sec_info['header_row']}"]
            h_cell.value = f"=SUM(H{sec_info['first_item']}:H{sec_info['last_item']})"
            h_cell.font = SUM_FONT
            h_cell.number_format = '#,##0.00'
            h_cell.alignment = Alignment(horizontal="right", vertical="center")

        ws.column_dimensions["I"].width = 3
        ws.column_dimensions["J"].width = 26
        ws.column_dimensions["K"].width = 20

        j1 = ws["J1"]
        j1.value = "COMPROBACION"
        j1.font = COMPROBACION_FONT
        j1.fill = COMPROBACION_FILL
        j1.alignment = Alignment(horizontal="center", vertical="center")
        j1.border = THIN
        ws["K1"].fill = COMPROBACION_FILL
        ws["K1"].border = THIN
        ws.merge_cells("J1:K1")

        ac_row  = section_rows.get("ACTIVO CIRCULANTE",  {}).get("header_row")
        af_row  = section_rows.get("ACTIVO FIJO",         {}).get("header_row")
        ad_row  = section_rows.get("ACTIVO DIFERIDO",     {}).get("header_row")
        pc_row  = section_rows.get("PASIVO CIRCULANTE",   {}).get("header_row")
        plp_row = section_rows.get("PASIVO LARGO PLAZO",  {}).get("header_row")
        cc_row  = section_rows.get("CAPITAL CONTABLE",    {}).get("header_row")

        verification = [
            ("Total Activos",            f"=H{ac_row}+H{af_row}+H{ad_row}" if ac_row and af_row and ad_row else ""),
            ("Total Pasivos",            f"=H{pc_row}+H{plp_row}"           if pc_row and plp_row         else ""),
            ("Capital Contable",         f"=H{cc_row}"                       if cc_row                     else ""),
            ("Activo-(Pasivo+Capital)", "=K2-(K3+K4)"),
        ]

        for i, (label, formula) in enumerate(verification, start=2):
            j = ws[f"J{i}"]
            j.value = label
            j.font = Font(bold=True, size=10)
            j.alignment = Alignment(horizontal="left", vertical="center")
            j.border = THIN
            j.fill = RESULT_FILL

            k = ws[f"K{i}"]
            k.value = formula
            k.font = RESULT_FONT
            k.number_format = '#,##0.00'
            k.alignment = Alignment(horizontal="right", vertical="center")
            k.border = THIN
            k.fill = RESULT_FILL

        ws["J6"].value = "Resultado:"
        ws["J6"].font = Font(bold=True, size=10)
        ws["J6"].alignment = Alignment(horizontal="left", vertical="center")
        ws["J6"].border = THIN
        ws["K6"].value = '=IF(ABS(K5)<0.01,"SI CUADRA","NO CUADRA")'
        ws["K6"].font = Font(bold=True, size=11)
        ws["K6"].alignment = Alignment(horizontal="center", vertical="center")
        ws["K6"].border = THIN

    return wb
