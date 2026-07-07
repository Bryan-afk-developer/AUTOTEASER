import fitz  # PyMuPDF
import io
import re
import logging
from app.llm_processor import configure_gemini
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import documentai

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def extract_name_from_ine(file_path: str = None, file_bytes: bytes = None, filename: str = "") -> str:
    """
    Lee un documento (PDF o imagen) de un INE, y extrae el nombre
    usando Gemini 1.5 Flash. Tiene un Fallback automático a Document AI.
    Puede recibir un file_path o directamente los file_bytes y filename.
    """
    try:
        img_bytes = None
        mime_type = "image/png"
        
        # Determinar el nombre del archivo para saber si es PDF
        actual_filename = file_path if file_path else filename
        
        # Extraemos la imagen si es PDF o la leemos directo si es JPG/PNG
        if actual_filename.lower().endswith('.pdf'):
            if file_path:
                doc = fitz.open(file_path)
            else:
                doc = fitz.open("pdf", file_bytes)
                
            if len(doc) > 0:
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
            doc.close()
        else:
            if file_path:
                with open(file_path, "rb") as f:
                    img_bytes = f.read()
            else:
                img_bytes = file_bytes
                
            if actual_filename.lower().endswith('.jpg') or actual_filename.lower().endswith('.jpeg'):
                mime_type = "image/jpeg"

        if not img_bytes:
            return "Error al leer documento"

        # Usar directamente Document AI como solicitó el usuario
        logger.info("Enviando INE a Document AI OCR básico...")
        return _extract_with_document_ai(img_bytes, mime_type)

    except Exception as e:
        logger.error(f"Error fatal procesando INE: {e}")
        return "Nombre no detectado"

def _extract_with_gemini(img_bytes: bytes, mime_type: str) -> str:
    """Usa la API de Gemini para extraer el nombre con un prompt estricto."""
    configure_gemini()
    
    model = GenerativeModel("gemini-2.5-flash")
    
    prompt = (
        "Extrae el nombre completo de la persona de esta credencial oficial (INE de México). "
        "Toma en cuenta que en las credenciales INE el nombre suele estar en varias líneas debajo de la etiqueta 'NOMBRE': "
        "primero el apellido paterno, luego el apellido materno y al final el nombre(s). "
        "Debes concatenar todo en una sola línea en orden lógico (Nombre(s) Apellido_Paterno Apellido_Materno). "
        "Devuelve ÚNICAMENTE el nombre completo en mayúsculas, sin texto adicional, sin introducciones, "
        "sin etiquetas y sin comillas. Ejemplo: JORGE VALES BULIO."
    )
    
    image_part = Part.from_data(data=img_bytes, mime_type=mime_type)
    
    response = model.generate_content(
        [prompt, image_part],
        generation_config={
            "temperature": 0.0, # Determinístico
            "max_output_tokens": 50,
        }
    )
    
    result = response.text.strip().upper()
    
    # Validamos que no nos haya respondido algo raro muy largo
    if len(result) > 100 or len(result) < 5:
        raise ValueError("Respuesta de Gemini inválida o muy larga")
        
    return result

def _extract_with_document_ai(img_bytes: bytes, mime_type: str) -> str:
    """Fallback usando Google Cloud Document AI."""
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("No se pudo usar Document AI para el INE: Faltan variables GCP")
        return "Nombre no detectado"
        
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)
    
    # Algunas versiones de Document AI prefieren application/pdf, pero acepta imágenes.
    raw_document = documentai.RawDocument(content=img_bytes, mime_type=mime_type)
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    
    result = client.process_document(request=request)
    text = result.document.text
    
    return _parse_ine_text(text)

def _parse_ine_text(ocr_text: str) -> str:
    """Lógica para parsear el texto de Document AI, buscando la etiqueta NOMBRE."""
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    nombre_completo = []
    
    for i, line in enumerate(lines):
        if "NOMBRE" in line.upper() or "NOMBPE" in line.upper():
            for j in range(1, 4):
                if i + j < len(lines):
                    if any(k in lines[i+j].upper() for k in ["DOMICILIO", "EDAD", "SEXO", "CLAVE"]):
                        break
                    nombre_completo.append(lines[i + j])
            break
            
    if nombre_completo:
        clean_name = " ".join([re.sub(r'[^A-ZÑÁÉÍÓÚ\s]', '', n.upper()).strip() for n in nombre_completo])
        return re.sub(r'\s+', ' ', clean_name)
        
    return "Nombre no detectado"
