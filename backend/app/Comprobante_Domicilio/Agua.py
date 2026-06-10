import logging
import re

logger = logging.getLogger(__name__)

def matches(text: str) -> bool:
    """Returns True if the PDF text looks like a Water bill."""
    text_upper = text.upper()
    return (
        "AGUA Y DRENAJE" in text_upper
        or "SADM" in text_upper
        or "COMISION DE AGUA" in text_upper
        or "SISTEMA DE AGUAS" in text_upper
        or "SACMEX" in text_upper
    )

def parse(text: str, img_bytes: bytes, mime_type: str) -> str:
    """
    Parses a Water bill to extract the address.
    """
    logger.info("Módulo Agua: Procesando recibo de agua...")
    
    from app.Comprobante_Domicilio import Generic_CD
    return Generic_CD.parse(text, img_bytes, mime_type)
