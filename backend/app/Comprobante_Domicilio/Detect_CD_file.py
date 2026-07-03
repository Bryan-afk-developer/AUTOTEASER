"""
AutoTeaser - CD File Detector
Router pattern for Comprobante de Domicilio processing.
"""
import logging
from app.Comprobante_Domicilio import CFE, Agua, Telmex, Telcel, Generic_CD

logger = logging.getLogger(__name__)

def detect_and_parse_cd(text: str, img_bytes: bytes, mime_type: str) -> str:
    """
    Ruta el recibo al módulo correspondiente según su contenido.
    Retorna la cadena "PROVEEDOR - DIRECCION".
    """
    if not text and not img_bytes:
        return "Ubicacion no detectada"

    # Si hay texto, intentamos rutearlo
    if text:
        if CFE.matches(text):
            return CFE.parse(text, img_bytes, mime_type)
            
        if Agua.matches(text):
            return Agua.parse(text, img_bytes, mime_type)
            
        if Telmex.matches(text):
            return Telmex.parse(text, img_bytes, mime_type)
            
        if Telcel.matches(text):
            return Telcel.parse(text, img_bytes, mime_type)
            
    # Si no hubo match, o si solo había imagen (sin texto), usamos el Genérico
    logger.info("Módulo CD: No se detectó proveedor específico, enviando a Generic_CD.")
    return Generic_CD.parse(text, img_bytes, mime_type)
