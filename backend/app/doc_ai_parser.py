import logging
import re
from pathlib import Path
from google.cloud import documentai

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR
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

def parse_pdf_with_doc_ai(pdf_path: str, year: str = "2024") -> dict:
    """
    Uses Google Cloud Document AI (Form Parser) to parse a scanned PDF.
    Extracts key-value pairs and maps them to the AutoCAF schema.
    """
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("DocAI variables (GCP_PROJECT_ID, GCP_PROCESSOR_ID_OCR) are not set.")
        return {"success": False, "method": "document_ai", "data": {}}

    logger.info(f"AutoCAF: Falling back to Document AI OCR for {pdf_path}")
    
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)

    try:
        import fitz
        doc_pdf = fitz.open(pdf_path)
        
        relevant_pages = list(range(len(doc_pdf)))
        
        if len(doc_pdf) > 15:
            logger.info(f"DocAI: PDF has {len(doc_pdf)} pages. Using smart page selection to stay under 15-page limit.")
            keywords = ["balance", "estado de resultados", "capital", "resultados", "pasivo", "activo"]
            relevant_pages = []
            
            for i in range(len(doc_pdf)):
                text = doc_pdf[i].get_text().lower()
                
                # If no native text, use OCR to check keywords
                if not text.strip():
                    try:
                        from app.pdf_extractor_caf import _ocr_page
                        text = _ocr_page(doc_pdf[i], dpi=150).lower()
                    except Exception:
                        pass
                        
                if any(kw in text for kw in keywords):
                    relevant_pages.append(i)
                    
            if not relevant_pages:
                # Fallback if no keywords found (e.g. OCR failed)
                relevant_pages = list(range(5)) + list(range(len(doc_pdf) - 10, len(doc_pdf)))
            elif len(relevant_pages) > 15:
                # Prioritize first few pages if we have too many
                relevant_pages = relevant_pages[:15]
                
            new_doc = fitz.open()
            for p in relevant_pages:
                new_doc.insert_pdf(doc_pdf, from_page=p, to_page=p)
            image_content = new_doc.write()
            new_doc.close()
            logger.info(f"DocAI: Selected pages for processing: {relevant_pages}")
        else:
            with open(pdf_path, "rb") as image:
                image_content = image.read()
        
        raw_document = documentai.RawDocument(content=image_content, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document
        
        # --- GENERATE SEARCHABLE PDF ---
        try:
            # We iterate the Document AI pages. 
            # DocAI page index 'i' maps to original PDF page index 'relevant_pages[i]'
            for i, page_ai in enumerate(document.pages):
                if i >= len(relevant_pages):
                    break
                orig_p_num = relevant_pages[i]
                page_pdf = doc_pdf[orig_p_num]
                page_width = page_pdf.rect.width
                page_height = page_pdf.rect.height
                
                for token in page_ai.tokens:
                    token_text = _layout_to_text(token.layout, document.text).strip()
                    if not token_text: continue
                    
                    vertices = token.layout.bounding_poly.normalized_vertices
                    if not vertices or len(vertices) != 4: continue
                    
                    x0 = min(v.x for v in vertices) * page_width
                    y0 = min(v.y for v in vertices) * page_height
                    x1 = max(v.x for v in vertices) * page_width
                    y1 = max(v.y for v in vertices) * page_height
                    
                    # Some padding/sanity checks to prevent crashes
                    if x0 >= x1 or y0 >= y1: continue
                    rect = fitz.Rect(x0, y0, x1, y1)
                    
                    # Insert invisible text (render_mode=3)
                    page_pdf.insert_textbox(rect, token_text, fontsize=10, render_mode=3)
            
            # Save the modified PDF
            searchable_path = Path(pdf_path).with_name(f"{Path(pdf_path).stem}_searchable.pdf")
            doc_pdf.save(str(searchable_path))
            logger.info(f"DocAI: Generated searchable PDF at {searchable_path}")
        except Exception as e_pdf:
            logger.error(f"DocAI: Failed to generate searchable PDF: {e_pdf}")
            searchable_path = None
        
        doc_pdf.close()
        
    except Exception as e:
        logger.error(f"DocAI Error processing {pdf_path}: {e}")
        return {"success": False, "method": "document_ai", "data": {}}

    # Try to find the actual year from the OCR text
    from app.deterministic_parser import _find_year_in_text
    extracted_year = _find_year_in_text(document.text)
    if extracted_year:
        year = extracted_year
        
    # Reconstruct lines visually to defeat multi-column layout issues
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
            
        import re
        
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
                        except:
                            pass
                    
                    text = w['text']
                    # Wrap tokens containing digits in pipes to prevent regex space-concatenation
                    if re.search(r'\d', text):
                        filtered_line.append(f"| {text} |")
                    else:
                        filtered_line.append(text)
                
                # Join with spaces so multi-word text keywords match perfectly
                line_str = ' '.join(filtered_line)
                all_lines.append(line_str.lower())
                
        process_half(left_words)
        process_half(right_words)
            
    balance_data = {}
    edo_data = {}
    
    # --- Extract Balance Data ---
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

    # --- Extract Edo Data ---
    for key, keywords in EDO_TOTAL_KEYWORDS.items():
        val = _find_value(all_lines, keywords, header_mode=True)
        edo_data[key] = abs(val)

    for key, keywords in EDO_LINE_KEYWORDS.items():
        val = _find_value(all_lines, keywords, header_mode=False)
        edo_data[key] = abs(val)

    # ── Mathematical Validation (Activo = Pasivo + Capital) ──
    activo_circulante = ["caja", "bancos", "clientes", "cuentas_por_cobrar", "deudores_diversos", "isr_diferido", "inventarios", "pagos_anticipados", "anticipo_proveedores", "impuestos_a_favor"]
    activo_fijo = ["edificios", "maquinaria_equipo", "equipo_transporte", "mobiliario_equipo", "equipo_computo", "otros_activos_fijos", "terrenos"]
    activo_diferido = ["gastos_instalacion", "depositos_garantia", "otros_activos_largo_plazo"]
    
    total_activo = sum(balance_data.get(k, 0) for k in activo_circulante + activo_fijo + activo_diferido) - balance_data.get("depreciacion_acumulada", 0)
    
    pasivo_cp = ["proveedores", "prestamos_bancarios_cp", "acreedores_diversos", "otros_pasivos_cp", "anticipo_clientes", "impuestos_acumulados"]
    pasivo_lp = ["prestamos_bancarios_lp", "otras_cuentas_lp"]
    total_pasivo = sum(balance_data.get(k, 0) for k in pasivo_cp + pasivo_lp)
    
    capital_fields = ["capital_social", "reserva_legal", "aportaciones_futuros_aumentos", "utilidad_ejercicio"]
    total_capital_sin_ea = sum(balance_data.get(k, 0) for k in capital_fields)
    
    current_ejercicios_anteriores = balance_data.get("resultados_ejercicios_anteriores", 0)
    diff = total_activo - (total_pasivo + total_capital_sin_ea + current_ejercicios_anteriores)
    
    warnings = []
    if abs(diff) > 1.0 and total_activo > 0:
        logger.warning(f"DocAI: Discrepancia detectada. Activo ({total_activo}) != Pasivo ({total_pasivo}) + Capital ({total_capital_sin_ea + current_ejercicios_anteriores}). Diferencia: {diff}")
        
        warnings.append({
            "type": "balance_mismatch",
            "severity": "high",
            "message": f"El balance no cuadra por {diff:,.2f}. No se realizó ningún ajuste automático.",
            "diff": diff
        })

    # Final structure
    return {
        "success": True,
        "method": "Document AI Form Parser (Fallback)",
        "data": {
            "Balance": {
                year: balance_data
            },
            "Edo de resultados": {
                year: edo_data
            }
        },
        "raw_text_dump": all_lines,
        "searchable_pdf_path": str(searchable_path) if 'searchable_path' in locals() and searchable_path else None,
        "warnings": warnings
    }
