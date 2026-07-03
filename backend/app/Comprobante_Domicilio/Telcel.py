import logging
import re
from app.Comprobante_Domicilio import Generic_CD

logger = logging.getLogger(__name__)

def matches(text: str) -> bool:
    """Returns True if the PDF text looks like a Telcel bill."""
    text_upper = text.upper()
    return "TELCEL" in text_upper or "RADIOMOVIL DIPSA" in text_upper

def parse(text: str, img_bytes: bytes, mime_type: str) -> str:
    """
    Parses a Telcel bill to extract the address.
    """
    logger.info("Módulo Telcel: Procesando recibo de telefonía móvil...")
    
    # 1. Intento de extracción por Regex
    if text:
        # En Telcel usualmente la dirección viene bajo "Lugar de Expedición" o el nombre del titular.
        # Buscamos patrones típicos de dirección (CP de 5 dígitos, Colonia, etc.)
        # Este es un regex muy básico como primera línea de defensa
        match = re.search(r'(?:Expedici[oó]n|Direcci[oó]n|Domicilio)[:\s]*([^\n]+C\.?P\.?\s*\d{5}[^\n]*)', text, re.IGNORECASE)
        if match:
            direccion = match.group(1).strip()
            # Limpiar basura extra si es necesario
            direccion = re.sub(r'\s+', ' ', direccion)
            if len(direccion) > 10:
                logger.info("Módulo Telcel: Dirección extraída por Regex exitosamente.")
                return f"Telcel - {direccion}"

    # 2. Fallback a Gemini si el Regex no funcionó (el formato cambió o está muy sucio)
    logger.info("Módulo Telcel: Regex no concluyente, usando IA como fallback...")
    
    try:
        # Usamos el extractor de IA enviándole un hint de que es Telcel
        return Generic_CD.parse(text, img_bytes, mime_type)
    except Exception as e:
        logger.error(f"Error en Módulo Telcel fallback: {e}")
        return "Telcel - Ubicacion no detectada"
