import logging
import re
from pathlib import Path
from app.pdf_extractor import extract_with_documentai

logger = logging.getLogger(__name__)

def extraer_score_de_bytes(pdf_source: Path | str | bytes) -> dict:
    """
    Extrae el "Mi Score" de un reporte de Buró de Crédito Score.
    Utiliza Document AI para extraer el texto y luego busca el puntaje.
    """
    try:
        if isinstance(pdf_source, str):
            pdf_source = Path(pdf_source)
            
        if isinstance(pdf_source, Path) and not pdf_source.exists():
            logger.error(f"Archivo no encontrado: {pdf_source}")
            return {"score": None, "error": "Archivo no encontrado"}

        # Extract text via DocAI
        docai_pages = extract_with_documentai(pdf_source)
        if not docai_pages:
            logger.error("No se pudo extraer texto del PDF con Document AI.")
            return {"score": None, "error": "No se pudo extraer el texto"}
            
        full_text = "\n".join(docai_pages)
        
        # Method 1: Look for the number right before "El X% de la población"
        match = re.search(r'(\d{3})\s*El \d+% de la poblaci[oó]n', full_text, re.IGNORECASE)
        if match:
            return {"score": int(match.group(1)), "error": None}
            
        # Method 2: Find all 3-digit numbers between 300 and 900.
        # The gauge usually has 356 (min) and 848 (max). The score is the other one.
        numbers = [int(n) for n in re.findall(r'\b(\d{3})\b', full_text)]
        valid_scores = [n for n in numbers if 300 <= n <= 900]
        
        # Filter out the gauge limits if possible, or pick the one that appears alongside them
        candidates = [n for n in valid_scores if n not in (356, 848)]
        if candidates:
            return {"score": candidates[0], "error": None}
            
        # If no candidates but we found 356 or 848 multiple times, the score might be exactly the limit
        if valid_scores.count(356) >= 2:
            return {"score": 356, "error": None}
        if valid_scores.count(848) >= 2:
            return {"score": 848, "error": None}
            
        logger.warning("No se encontró el Score en el documento.")
        return {"score": None, "error": "No se encontró el Score"}

    except Exception as e:
        logger.error(f"Error extrayendo Score: {e}")
        return {"score": None, "error": str(e)}

def extraer_score_desde_storage(storage_path: str, supabase_client) -> dict:
    """Descarga el PDF de Buró Score desde Supabase Storage y extrae el Score."""
    try:
        pdf_bytes = supabase_client.storage.from_("expedientes_clientes").download(storage_path)
    except Exception as e:
        logger.error(f"Error descargando BC Score desde Storage ({storage_path}): {e}")
        return {"score": None, "error": f"No se pudo descargar: {e}"}

    return extraer_score_de_bytes(pdf_bytes)
