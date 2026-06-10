import logging
import re

logger = logging.getLogger(__name__)

def matches(text: str) -> bool:
    """Returns True if the PDF text looks like a Telmex bill."""
    text_upper = text.upper()
    return (
        "TELMEX" in text_upper
        or "TELEFONOS DE MEXICO" in text_upper
        or "TELÉFONOS DE MÉXICO" in text_upper
    )

def parse(text: str, img_bytes: bytes, mime_type: str) -> str:
    """
    Parses a Telmex bill to extract the address.
    """
    logger.info("Módulo Telmex: Procesando recibo de teléfono...")
    
    from app.Comprobante_Domicilio import Generic_CD
    return Generic_CD.parse(text, img_bytes, mime_type)
