import fitz  # PyMuPDF
import io
import re
import logging
from app.llm_processor import configure_gemini
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import documentai

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def parse(extracted_text: str, img_bytes: bytes, mime_type: str) -> str:
    """
    Fallback method that uses Gemini to extract the address and provider from text or image.
    If Gemini fails, it falls back to Document AI.
    """
    try:
        if not extracted_text and not img_bytes:
            return "Ubicacion no detectada"

        # 2. Intento con Gemini
        try:
            return _extract_with_gemini(extracted_text, img_bytes, mime_type)
        except Exception as e:
            logger.warning(f"Error en Gemini al procesar Comprobante Domicilio: {e}. Activando Fallback a Document AI...")
            return _extract_with_document_ai(img_bytes, mime_type)

    except Exception as e:
        logger.error(f"Error fatal procesando Comprobante Domicilio (Genérico): {e}")
        return "Ubicacion no detectada"

def _clean_location_string(raw_text: str) -> str:
    """Limpia la respuesta de la IA para que sea válida para un nombre de archivo"""
    # Eliminar posibles etiquetas markdown o prefijos
    text = raw_text.replace("```json", "").replace("```", "").strip()
    text = text.replace('"', '').replace("Ubicacion:", "").replace("Direccion:", "").strip()
    
    # Eliminar caracteres inválidos para Windows/Linux filenames
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    # Limitar longitud para evitar problemas de file path muy largo
    if len(text) > 120:
        text = text[:117] + "..."
        
    return text.strip()

def _extract_with_gemini(extracted_text: str, img_bytes: bytes, mime_type: str) -> str:
    configure_gemini()
    model = GenerativeModel('gemini-2.5-flash')
    
    prompt = (
        "Eres un asistente experto en extraer datos de comprobantes de domicilio en México (CFE, Telmex, Agua, etc.). "
        "Extrae el proveedor del servicio y la dirección COMPLETA del CLIENTE (no la del emisor ni la de la sucursal) en este formato exacto: "
        "'PROVEEDOR - Calle #NumeroExterior, Colonia, Municipio, Estado, CP'. "
        "Ejemplo de respuesta ideal 1: 'CFE - Carr Nacional #5002, La Rioja, Monterrey, Nuevo León, 64988'. "
        "Ejemplo de respuesta ideal 2: 'Telmex - Av. Insurgentes #1500, Polanco, Miguel Hidalgo, CDMX, 11560'. "
        "No incluyas explicaciones, solo la respuesta en el formato solicitado."
    )

    if extracted_text:
        # Modo Texto (Searchable PDF)
        logger.info("Usando Gemini en modo Texto para el Comprobante de Domicilio")
        response = model.generate_content([prompt, f"Texto del recibo: {extracted_text}"])
    else:
        # Modo Visión (Scanned PDF o Imagen)
        logger.info("Usando Gemini en modo Visión para el Comprobante de Domicilio")
        image_part = Part.from_data(data=img_bytes, mime_type=mime_type)
        response = model.generate_content([prompt, image_part])

    text_result = response.text.strip()
    if not text_result:
        raise ValueError("Respuesta vacía de Gemini")
        
    return _clean_location_string(text_result)

def _extract_with_document_ai(raw_bytes: bytes, mime_type: str) -> str:
    """Fallback usando Google Cloud Document AI."""
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.error("No se pudo usar Document AI para el Comprobante Domicilio: Faltan variables GCP")
        return "Ubicacion no detectada"
        
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)

    raw_document = documentai.RawDocument(content=raw_bytes, mime_type=mime_type)
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    
    result = client.process_document(request=request)
    text = result.document.text
    
    # Buscar patrones de CPs, Estados, etc. Al no ser un LLM conversacional, es más ruidoso.
    # Como fallback básico, extraemos las primeras 80 letras que contengan números y texto cerca del final.
    # O mejor, pasamos ese texto extraído de nuevo a un prompt regex simple.
    
    # Para simplicidad, devolvemos un extracto truncado que parezca una dirección.
    lines = text.split('\n')
    direccion_candidata = ""
    for line in lines:
        if re.search(r'\bC\.?P\.?\s*\d{5}\b', line, re.IGNORECASE) or re.search(r'\bCol\.', line, re.IGNORECASE):
            direccion_candidata += line.strip() + " "
            
    if direccion_candidata:
        return _clean_location_string(direccion_candidata)
    
    # Si no encuentra un patrón obvio, retorna las primeras palabras
    return _clean_location_string(' '.join(lines[:3]))
