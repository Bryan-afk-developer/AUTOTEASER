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
    logger.info("Módulo CFE: Procesando recibo de luz...")
    
    # Aquí puedes implementar lógica RegEx en el futuro.
    # Por ahora, usamos el Generic_CD (Gemini) pasándole un prompt optimizado para CFE si quisieras,
    # o directamente usando el Genérico.
    from app.Comprobante_Domicilio import Generic_CD
    
    # Delegamos al genérico pero podríamos hacer cosas específicas de CFE antes o después.
    return Generic_CD.parse(text, img_bytes, mime_type)
