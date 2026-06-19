import logging
from extractor_native import extract_native_text
from doc_ai_parser import extract_with_doc_ai
from llm_processor import analyze_document

logger = logging.getLogger(__name__)

def process_document(pdf_path: str, doc_type_override: str = None) -> dict:
    """
    Función principal para procesar un documento (MOP, INE, Estado de Cuenta, etc).
    1. Extrae texto nativo (muy rápido, sin costo).
    2. Si el documento es una imagen o escaneado (poco texto), usa Document AI OCR.
    3. Analiza el texto con Gemini usando el prompt adecuado.
    """
    
    # 1. Intento de extracción nativa
    logger.info(f"Intentando extracción nativa para: {pdf_path}")
    raw_text = extract_native_text(pdf_path)
    
    # Heurística simple: si tiene menos de 100 caracteres, probablemente sea un escaneo o imagen
    if len(raw_text) < 100:
        logger.info("Poco texto nativo encontrado. Usando fallback a Google Document AI...")
        raw_text = extract_with_doc_ai(pdf_path)
        
        if len(raw_text) < 100:
            return {"error": "No se pudo extraer texto del documento (ni nativo ni OCR)."}
            
    # 2. Análisis con IA (Gemini)
    logger.info(f"Procesando texto extraído con Gemini...")
    result_json = analyze_document(raw_text, doc_type=doc_type_override)
    
    return result_json
