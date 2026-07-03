import fitz  # PyMuPDF
import logging

from app.Comprobante_Domicilio.Detect_CD_file import detect_and_parse_cd

logger = logging.getLogger(__name__)

def extract_location_from_cd(file_path: str = None, file_bytes: bytes = None, filename: str = "") -> str:
    """
    Punto de entrada principal para procesar un Comprobante de Domicilio.
    Lee el archivo, extrae texto/imagen y se lo pasa al enrutador (Detect_CD_file).
    """
    try:
        actual_filename = file_path if file_path else filename
        extracted_text = ""
        img_bytes = None
        mime_type = "image/png"

        # 1. Intentar extraer texto directamente con PyMuPDF
        if actual_filename.lower().endswith('.pdf'):
            if file_path:
                doc = fitz.open(file_path)
            else:
                doc = fitz.open("pdf", file_bytes)
            
            if len(doc) > 0:
                page = doc.load_page(0)
                extracted_text = page.get_text().strip()
                
                # Si no hay suficiente texto, es un PDF escaneado, sacar la imagen y usar Document AI
                if len(extracted_text) < 50:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    
                    try:
                        from app.pdf_extractor import extract_with_documentai
                        logger.info("PDF Escaneado detectado en CD, usando Document AI para extraer texto base.")
                        # Pass bytes or file_path
                        if file_path:
                            docai_text_list = extract_with_documentai(file_path)
                        else:
                            docai_text_list = extract_with_documentai(file_bytes)
                        extracted_text = "\n".join(docai_text_list)
                    except Exception as ex:
                        logger.warning(f"Fallo extracción OCR en CD: {ex}")
                        extracted_text = ""
                else:
                    # Siempre guardamos la imagen por si acaso el Document AI fallback la necesita
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
            doc.close()
        else:
            # Es una imagen directa
            if file_path:
                with open(file_path, "rb") as f:
                    img_bytes = f.read()
            else:
                img_bytes = file_bytes
                
            if actual_filename.lower().endswith('.jpg') or actual_filename.lower().endswith('.jpeg'):
                mime_type = "image/jpeg"

        # Pasar los datos extraídos al enrutador modular
        return detect_and_parse_cd(extracted_text, img_bytes, mime_type)

    except Exception as e:
        logger.error(f"Error fatal extrayendo Comprobante Domicilio: {e}")
        return "Ubicacion no detectada"
