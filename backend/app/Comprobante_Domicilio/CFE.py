import logging
import re

logger = logging.getLogger(__name__)

def matches(text: str) -> bool:
    """Returns True if the PDF text looks like a CFE bill."""
    text_upper = text.upper()
    # Check for CFE keywords
    return (
        "COMISION FEDERAL DE ELECTRICIDAD" in text_upper
        or "CFE" in text_upper
        or "KWH" in text_upper
        or "SUMINISTRO BASICO" in text_upper
    )

def parse(text: str, img_bytes: bytes, mime_type: str) -> str:
    """
    Parses a CFE bill to extract the address.
    For now, we route it to Gemini to extract the address cleanly using the Generic_CD logic,
    but in the future, you can implement purely regex-based extraction here without touching Gemini.
    """
    # 1. Intento de extracción por Regex
    if text:
        # En CFE, la dirección suele estar cerca de un código postal (C.P. XXXXX) y la ciudad.
        # Capturamos un bloque de texto que termine con un CP válido
        match = re.search(r'([A-Za-z0-9\s#.,]+?C\.?P\.?\s*\d{5}[A-Za-z0-9\s,.]*?)', text, re.IGNORECASE)
        # Nota: La extracción de CFE es compleja por el formato tabular. Si el Regex falla o trae basura, 
        # delegamos a la IA.
        
        # En el futuro puedes mejorar este regex analizando las líneas específicas de CFE (ej. encima de RMU)

    # 2. Fallback a Gemini si el Regex no es seguro
    logger.info("Módulo CFE: Usando IA como fallback para extraer dirección con precisión...")
    from app.Comprobante_Domicilio import Generic_CD
    
    return Generic_CD.parse(text, img_bytes, mime_type)
