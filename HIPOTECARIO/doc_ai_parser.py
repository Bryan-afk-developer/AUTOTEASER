import fitz
import logging
from google.cloud import documentai
from config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def extract_with_doc_ai(pdf_path: str) -> str:
    """
    Extrae texto de un PDF (escaneado o imagen) usando Google Document AI.
    """
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("Credenciales de Document AI no configuradas en el .env")
        return ""

    doc = fitz.open(pdf_path)
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)
    
    full_extracted_text = ""
    
    # Procesamos página por página (o se puede enviar el PDF entero si es menor a 15 pags)
    # Por seguridad y simplicidad, convertimos a imagen y mandamos
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Redimensionar para evitar errores 400 (muy grande)
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
        
        try:
            res = client.process_document(request=req)
            full_extracted_text += res.document.text + "\n\n"
        except Exception as e:
            logger.error(f"Error en Document AI en página {page_num}: {e}")
            
    doc.close()
    return full_extracted_text.strip()
