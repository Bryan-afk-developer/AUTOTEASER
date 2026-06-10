import io
import json
import logging
import base64
import re
from PIL import Image as PILImage
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path("templates/CAF - BRIGHTEC - 2026.02 - plantilla-balance (1).xlsx")
MAPA_PATH = Path("templates/mapa.json")

def _apply_header_style(cell):
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")
    thin = Side(border_style="thin", color="000000")
    cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)

def build_caf_excel(docs_data: list) -> bytes:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"No se encontró la plantilla en {TEMPLATE_PATH}")
    if not MAPA_PATH.exists():
        raise FileNotFoundError(f"No se encontró el mapa JSON en {MAPA_PATH}")
        
    with open(MAPA_PATH, "r", encoding="utf-8") as f:
        mapa = json.load(f)
        
    wb = load_workbook(TEMPLATE_PATH)
    
    for doc in docs_data:
        # Detectar el año
        year = str(doc.get("year", "")).strip()
        if year == "Desconocido" or not year:
            match = re.search(r'\b(20[1-2][0-9])\b', doc.get("filename", ""))
            if match:
                year = match.group(1)
        
        if year == "Desconocido" or not year:
            # Si aún no hay año, usar un nombre temporal único
            import uuid
            year = f"Desc_{str(uuid.uuid4())[:4]}"
            
        sheet_name = year
        # Asegurar que el nombre de la hoja sea único
        original_sheet_name = sheet_name
        counter = 1
        while sheet_name in wb.sheetnames:
            sheet_name = f"{original_sheet_name}_{counter}"
            counter += 1
            
        ws_year = wb.create_sheet(title=sheet_name)
        
        # Headers para Inputs Estructurados
        ws_year["A1"] = "Concepto Financiero"
        ws_year["B1"] = "Input (Escribe aquí)"
        _apply_header_style(ws_year["A1"])
        _apply_header_style(ws_year["B1"])
        
        # Headers para Vaciado Crudo
        ws_year["D1"] = "Página"
        ws_year["E1"] = "Texto Extraído (Crudo)"
        ws_year["F1"] = "Evidencia Visual"
        _apply_header_style(ws_year["D1"])
        _apply_header_style(ws_year["E1"])
        _apply_header_style(ws_year["F1"])
        
        # Configurar anchos de columna
        ws_year.column_dimensions["A"].width = 30
        ws_year.column_dimensions["B"].width = 20
        ws_year.column_dimensions["C"].width = 5  # Espaciador
        ws_year.column_dimensions["D"].width = 10
        ws_year.column_dimensions["E"].width = 40
        ws_year.column_dimensions["F"].width = 60
        
        # --- PARTE 1: Construir Inputs y enlazar a Plantilla ---
        input_row = 2
        for template_sheet in ["Balance", "Edo de resultados"]:
            if template_sheet in mapa and year in mapa[template_sheet]:
                concepts = mapa[template_sheet][year]
                
                # Para cada concepto, crear una fila en la hoja del año
                for concept_name, target_cell in concepts.items():
                    ws_year[f"A{input_row}"] = concept_name
                    
                    # Formato para la celda de Input
                    input_cell = ws_year[f"B{input_row}"]
                    input_cell.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
                    input_cell.alignment = Alignment(horizontal="right", vertical="center")
                    input_cell.number_format = '#,##0.00'
                    thin = Side(border_style="thin", color="000000")
                    input_cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)
                    
                    # Conectar la hoja principal hacia este Input
                    if template_sheet in wb.sheetnames and target_cell:
                        ws_main = wb[template_sheet]
                        # Escribimos una fórmula para que apunte a nuestro input
                        # Ejemplo: ='2023'!B2
                        ws_main[target_cell] = f"='{sheet_name}'!B{input_row}"
                        
                    input_row += 1
        
        # --- PARTE 2: Vaciado Crudo con Imágenes ---
        data_row = 2
        if "extracted_data" in doc and "pages" in doc["extracted_data"]:
            for page in doc["extracted_data"]["pages"]:
                p_num = page.get("page_num", 0) + 1
                for table in page.get("tables", []):
                    for row in table:
                        if not row:
                            continue
                            
                        # Extraer texto de la fila
                        row_text = " | ".join(str(c.get("text", "")) for c in row if c and c.get("text"))
                        if not row_text.strip():
                            continue
                            
                        ws_year[f"D{data_row}"] = f"Pág {p_num}"
                        ws_year[f"E{data_row}"] = row_text
                        
                        # Alinear al centro
                        ws_year[f"D{data_row}"].alignment = Alignment(vertical="center", horizontal="center")
                        ws_year[f"E{data_row}"].alignment = Alignment(vertical="center", wrap_text=True)
                        
                        # Evidencia Visual
                        evidence_b64 = None
                        for cell in row:
                            if cell and cell.get("evidence_b64"):
                                evidence_b64 = cell["evidence_b64"]
                                break
                                
                        if evidence_b64:
                            try:
                                img_data = base64.b64decode(evidence_b64)
                                # Usar PIL para saber dimensiones
                                pil_img = PILImage.open(io.BytesIO(img_data))
                                w, h = pil_img.size
                                
                                # Escalar imagen (max width 300)
                                max_width = 300
                                if w > max_width:
                                    ratio = max_width / w
                                    w = max_width
                                    h = int(h * ratio)
                                    
                                xl_img = OpenpyxlImage(io.BytesIO(img_data))
                                xl_img.width = w
                                xl_img.height = h
                                
                                ws_year.add_image(xl_img, f"F{data_row}")
                                
                                # Ajustar altura de la fila (1 punto = 1.33 píxeles aprox)
                                ws_year.row_dimensions[data_row].height = max(15, h * 0.75 + 10)
                            except Exception as e:
                                logger.error(f"Error procesando imagen para Excel: {e}")
                        else:
                            ws_year.row_dimensions[data_row].height = 20
                            
                        data_row += 1

    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    
    return output_stream.read()
