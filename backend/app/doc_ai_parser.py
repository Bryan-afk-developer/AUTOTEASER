import logging
import re
from pathlib import Path
from google.cloud import documentai

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR, GCP_PROCESSOR_ID_BASIC_OCR
from app.deterministic_parser import (
    _normalize, BALANCE_MAP, BALANCE_HEADER_KEYS, EDO_TOTAL_KEYWORDS,
    EDO_LINE_KEYWORDS, _parse_number, _find_value
)

logger = logging.getLogger(__name__)

def _layout_to_text(layout, text: str) -> str:
    """Extracts text from a Document AI layout object based on text anchors."""
    response = ""
    if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
        return ""
    for segment in layout.text_anchor.text_segments:
        start_index = int(segment.start_index) if segment.start_index else 0
        end_index = int(segment.end_index)
        response += text[start_index:end_index]
    return response.strip()


def _overlay_docai_text_on_pdf(doc_pdf, document, page_index_map: list):
    """
    Overlay invisible OCR tokens from a Document AI result onto the open fitz document.
    page_index_map: maps DocAI page index → original PDF page index.
    """
    import fitz
    for i, page_ai in enumerate(document.pages):
        if i >= len(page_index_map):
            break
        orig_p_num = page_index_map[i]
        page_pdf = doc_pdf[orig_p_num]
        page_width = page_pdf.rect.width
        page_height = page_pdf.rect.height

        for token in page_ai.tokens:
            token_text = _layout_to_text(token.layout, document.text).strip()
            if not token_text:
                continue

            vertices = token.layout.bounding_poly.normalized_vertices
            if not vertices or len(vertices) < 2:
                continue

            xs = [v.x for v in vertices]
            ys = [v.y for v in vertices]
            x0 = min(xs) * page_width
            y0 = min(ys) * page_height
            x1 = max(xs) * page_width
            y1 = max(ys) * page_height

            if x0 >= x1 or y0 >= y1:
                continue

            box_h = y1 - y0
            box_w = x1 - x0
            fontsize = max(4, box_h * 0.72)
            estimated_text_w = len(token_text) * fontsize * 0.5
            if estimated_text_w > box_w and estimated_text_w > 0:
                fontsize = max(4, fontsize * (box_w / estimated_text_w))

            baseline_y = y1 - box_h * 0.1

            try:
                page_pdf.insert_text(
                    fitz.Point(x0, baseline_y),
                    token_text,
                    fontsize=fontsize,
                    render_mode=3,  # invisible but searchable
                )
            except Exception:
                try:
                    page_pdf.insert_text(
                        fitz.Point(x0, baseline_y),
                        token_text,
                        fontsize=8,
                        render_mode=3,
                    )
                except Exception:
                    pass


def generate_searchable_pdf(pdf_path: str, _document=None, _relevant_pages=None) -> str | None:
    """
    Overlay invisible OCR text onto ALL pages of the original PDF.
    Recycles the pre-extracted data (_document) for the first N pages to save costs,
    then processes only the remaining pages using the cheaper Document OCR API.
    Runs as a FastAPI BackgroundTask.
    """
    if not GCP_PROJECT_ID or not (GCP_PROCESSOR_ID_BASIC_OCR or GCP_PROCESSOR_ID_OCR):
        logger.error("DocAI: Cannot generate searchable PDF — GCP variables not set.")
        return None

    try:
        import fitz
        doc_pdf = fitz.open(pdf_path)
        n_pages = len(doc_pdf)
        BATCH_SIZE = 15

        # 1. Recycle already extracted pages to save costs
        processed_pages = set()
        if _document and _relevant_pages is not None:
            logger.info(f"DocAI Searchable: Recycling {len(_relevant_pages)} pages from Form Parser step to save costs.")
            try:
                _overlay_docai_text_on_pdf(doc_pdf, _document, _relevant_pages)
                processed_pages.update(_relevant_pages)
            except Exception as e:
                logger.error(f"DocAI Searchable: Failed to recycle pre-extracted pages: {e}")

        # 2. Identify pages that still need OCR
        pages_to_process = [p for p in range(n_pages) if p not in processed_pages]
        
        if pages_to_process:
            logger.info(f"DocAI Searchable: {len(pages_to_process)} pages remaining. Using cheaper Document OCR.")
            opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
            client = documentai.DocumentProcessorServiceClient(client_options=opts)
            
            # Use Basic OCR if available, fallback to Form Parser ID if not set
            processor_id = GCP_PROCESSOR_ID_BASIC_OCR if GCP_PROCESSOR_ID_BASIC_OCR else GCP_PROCESSOR_ID_OCR
            name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, processor_id)

            # Process remaining pages in batches of ≤15
            for i in range(0, len(pages_to_process), BATCH_SIZE):
                batch_pages = pages_to_process[i:i + BATCH_SIZE]
                logger.info(f"DocAI Searchable: Processing missing batch {batch_pages} ({len(batch_pages)} pages) with Basic OCR")

                # Build sub-PDF for this batch
                batch_doc = fitz.open()
                for p in batch_pages:
                    batch_doc.insert_pdf(doc_pdf, from_page=p, to_page=p)
                batch_bytes = batch_doc.write()
                batch_doc.close()

                try:
                    raw_document = documentai.RawDocument(content=batch_bytes, mime_type="application/pdf")
                    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
                    result = client.process_document(request=request)
                    _overlay_docai_text_on_pdf(doc_pdf, result.document, batch_pages)
                except Exception as e:
                    logger.warning(f"DocAI Searchable: Batch {batch_pages} failed: {e}")
                    # Continue with next batch even if one fails

        searchable_path = Path(pdf_path).with_name(f"{Path(pdf_path).stem}_searchable.pdf")
        doc_pdf.save(str(searchable_path))
        doc_pdf.close()
        logger.info(f"DocAI: Searchable PDF ({n_pages} pages) saved at {searchable_path}")
        return str(searchable_path)

    except Exception as e:
        logger.error(f"DocAI: Failed to generate searchable PDF: {e}")
        return None


def parse_pdf_with_doc_ai(pdf_path: str, year: str = "2024") -> dict:
    """
    Uses Google Cloud Document AI (Form Parser) to parse a scanned PDF.
    Extracts key-value pairs and maps them to the AutoCAF schema.
    The searchable PDF is NOT generated here — call generate_searchable_pdf() separately
    (ideally as a BackgroundTask) using the '_docai_document' and '_relevant_pages' from the result.
    """
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("DocAI variables (GCP_PROJECT_ID, GCP_PROCESSOR_ID_OCR) are not set.")
        return {"success": False, "method": "document_ai", "data": {}}

    logger.info(f"AutoCAF: Falling back to Document AI OCR for {pdf_path}")

    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)

    # ── Page selection ──────────────────────────────────────────────────────────
    try:
        import fitz
        doc_pdf = fitz.open(pdf_path)
        n_pages = len(doc_pdf)
        relevant_pages = list(range(n_pages))

        if n_pages > 15:
            logger.info(f"DocAI: PDF has {n_pages} pages. Smart page selection (native text only).")
            keywords = ["balance", "estado de resultados", "capital", "resultados", "pasivo", "activo"]
            relevant_pages = []

            for i in range(n_pages):
                # Only check native text — NO pytesseract (not installed, wastes time)
                text = doc_pdf[i].get_text().lower()
                if any(kw in text for kw in keywords):
                    relevant_pages.append(i)

            if not relevant_pages:
                # Fully scanned PDF — take first 12 pages (balance + edo almost always there)
                relevant_pages = list(range(min(12, n_pages)))
                logger.info(f"DocAI: No native text found. Using first {len(relevant_pages)} pages.")
            elif len(relevant_pages) > 15:
                relevant_pages = relevant_pages[:15]

            new_doc = fitz.open()
            for p in relevant_pages:
                new_doc.insert_pdf(doc_pdf, from_page=p, to_page=p)
            image_content = new_doc.write()
            new_doc.close()
            logger.info(f"DocAI: Selected pages for processing: {relevant_pages}")
        else:
            with open(pdf_path, "rb") as f:
                image_content = f.read()

        doc_pdf.close()

    except Exception as e:
        logger.error(f"DocAI: Error reading/selecting PDF pages: {e}")
        return {"success": False, "method": "document_ai", "data": {}}

    # ── Document AI API call ────────────────────────────────────────────────────
    try:
        raw_document = documentai.RawDocument(content=image_content, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document
    except Exception as e:
        logger.error(f"DocAI: API call failed: {e}")
        return {"success": False, "method": "document_ai", "data": {}}

    # ── Year detection ──────────────────────────────────────────────────────────
    from app.deterministic_parser import _find_year_in_text
    extracted_year = _find_year_in_text(document.text)
    if extracted_year:
        year = extracted_year

    # ── Reconstruct lines visually (defeat multi-column layout) ────────────────
    all_lines = []
    for page in document.pages:
        left_words = []
        right_words = []
        for token in page.tokens:
            token_text = _layout_to_text(token.layout, document.text)
            vertices = token.layout.bounding_poly.normalized_vertices
            if not vertices:
                continue
            y_center = sum([v.y for v in vertices]) / len(vertices)
            x_center = sum([v.x for v in vertices]) / len(vertices)

            # Drop percentages to prevent rightmost_number from grabbing them
            if '%' in token_text:
                continue

            word_data = {'text': token_text, 'x': x_center, 'y': y_center}
            if x_center < 0.5:
                left_words.append(word_data)
            else:
                right_words.append(word_data)

        def process_half(words_list):
            lines = []
            words_list = sorted(words_list, key=lambda w: w['y'])
            for w in words_list:
                added = False
                for line in lines:
                    if abs(line[0]['y'] - w['y']) < 0.005:
                        line.append(w)
                        added = True
                        break
                if not added:
                    lines.append([w])

            lines = sorted(lines, key=lambda l: l[0]['y'])
            for line in lines:
                sorted_line = sorted(line, key=lambda w: w['x'])

                # Filter out obvious percentage values that lost their % sign
                filtered_line = []
                for i, w in enumerate(sorted_line):
                    if i == len(sorted_line) - 1:
                        try:
                            val = float(w['text'].replace(',', ''))
                            if val < 100.0 and '.' in w['text']:
                                continue
                        except Exception:
                            pass

                    text = w['text']
                    # Wrap tokens containing digits in pipes to prevent regex space-concatenation
                    if re.search(r'\d', text):
                        filtered_line.append(f"| {text} |")
                    else:
                        filtered_line.append(text)

                line_str = ' '.join(filtered_line)
                all_lines.append(line_str.lower())

        process_half(left_words)
        process_half(right_words)

    # ── Extract Balance Data ────────────────────────────────────────────────────
    balance_data = {}
    edo_data = {}

    for key, keywords in BALANCE_MAP.items():
        if key in ("resultados_ejercicios_anteriores", "utilidad_ejercicio"):
            continue
        is_header = key in BALANCE_HEADER_KEYS
        val = _find_value(all_lines, keywords, header_mode=is_header)
        balance_data[key] = abs(val)

    for key in ("resultados_ejercicios_anteriores", "utilidad_ejercicio"):
        keywords = BALANCE_MAP[key]
        val = _find_value(all_lines, keywords, header_mode=False)
        balance_data[key] = val

    # ── Extract Edo Data ────────────────────────────────────────────────────────
    for key, keywords in EDO_TOTAL_KEYWORDS.items():
        val = _find_value(all_lines, keywords, header_mode=True)
        edo_data[key] = abs(val)

    for key, keywords in EDO_LINE_KEYWORDS.items():
        val = _find_value(all_lines, keywords, header_mode=False)
        edo_data[key] = abs(val)

    # ── Mathematical Validation (Activo = Pasivo + Capital) ────────────────────
    activo_circulante = ["caja", "bancos", "clientes", "cuentas_por_cobrar", "deudores_diversos",
                         "isr_diferido", "inventarios", "pagos_anticipados", "anticipo_proveedores",
                         "impuestos_a_favor"]
    activo_fijo = ["edificios", "maquinaria_equipo", "equipo_transporte", "mobiliario_equipo",
                   "equipo_computo", "otros_activos_fijos", "terrenos"]
    activo_diferido = ["gastos_instalacion", "depositos_garantia", "otros_activos_largo_plazo"]

    total_activo = (sum(balance_data.get(k, 0) for k in activo_circulante + activo_fijo + activo_diferido)
                    - balance_data.get("depreciacion_acumulada", 0))

    pasivo_cp = ["proveedores", "prestamos_bancarios_cp", "acreedores_diversos",
                 "otros_pasivos_cp", "anticipo_clientes", "impuestos_acumulados"]
    pasivo_lp = ["prestamos_bancarios_lp", "otras_cuentas_lp"]
    total_pasivo = sum(balance_data.get(k, 0) for k in pasivo_cp + pasivo_lp)

    capital_fields = ["capital_social", "reserva_legal", "aportaciones_futuros_aumentos",
                      "utilidad_ejercicio"]
    total_capital_sin_ea = sum(balance_data.get(k, 0) for k in capital_fields)

    current_ejercicios_anteriores = balance_data.get("resultados_ejercicios_anteriores", 0)
    diff = total_activo - (total_pasivo + total_capital_sin_ea + current_ejercicios_anteriores)

    warnings = []
    if abs(diff) > 1.0 and total_activo > 0:
        logger.warning(
            f"DocAI: Discrepancia detectada. Activo ({total_activo}) != "
            f"Pasivo ({total_pasivo}) + Capital ({total_capital_sin_ea + current_ejercicios_anteriores}). "
            f"Diferencia: {diff}"
        )
        warnings.append({
            "type": "balance_mismatch",
            "severity": "high",
            "message": f"El balance no cuadra por {diff:,.2f}. No se realizó ningún ajuste automático.",
            "diff": diff
        })

    return {
        "success": True,
        "method": "Document AI Form Parser (Fallback)",
        "data": {
            "Balance": {year: balance_data},
            "Edo de resultados": {year: edo_data},
        },
        "raw_text_dump": {year: all_lines},
        # Pass these to main.py so BackgroundTask can recycle the already-parsed layout
        "_docai_document": document,
        "_relevant_pages": relevant_pages,
        "warnings": warnings,
    }
