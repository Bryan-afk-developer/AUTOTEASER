"""
AutoTeaser - SAT File Detector
Identifies if a PDF is a SAT Acuse de Recibo or a Declaración del Ejercicio.

Estructura de detección:
  1. Extrae texto del PDF con PyMuPDF
  2. Primero verifica si es Acuse (señales más específicas)
  3. Luego verifica si es Declaración
  4. Extrae el año fiscal del documento

Returns:
  {
    "tipo": "acuse" | "declaracion" | None,
    "year": "2025" | None
  }
"""
import logging

logger = logging.getLogger(__name__)

try:
    from app.SAT import Acuse, Declaracion
    SAT_AVAILABLE = True
except ImportError:
    try:
        from . import Acuse, Declaracion
        SAT_AVAILABLE = True
    except ImportError:
        SAT_AVAILABLE = False
        logger.warning("SAT detectors not available")


def detect_sat_document(text: str) -> dict:
    """
    Analyzes the extracted text from a PDF and determines if it's a SAT document.

    Args:
        text: Full extracted text from the PDF

    Returns:
        dict with:
          - tipo: "acuse", "declaracion", or None
          - year: "2025", "2024", etc. or None
    """
    result = {"tipo": None, "year": None, "is_complementaria": False}

    if not text or not SAT_AVAILABLE:
        return result

    # 1. Check for Acuse first (it's a shorter, distinct document)
    if Acuse.matches(text):
        parsed = Acuse.parse(text)
        result["tipo"] = "acuse"
        result["year"] = parsed.get("year")
        result["is_complementaria"] = parsed.get("is_complementaria", False)
        logger.info(f"SAT document detected: ACUSE - Año {result['year']}")
        return result

    # 2. Check for Declaración
    if Declaracion.matches(text):
        parsed = Declaracion.parse(text)
        result["tipo"] = "declaracion"
        result["year"] = parsed.get("year")
        result["is_complementaria"] = parsed.get("is_complementaria", False)
        logger.info(f"SAT document detected: DECLARACIÓN - Año {result['year']}")
        return result

    return result
