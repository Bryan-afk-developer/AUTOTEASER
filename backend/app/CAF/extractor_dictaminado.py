import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_dictaminado(pdf_path: str | Path, target_pages: list[int], page_layouts: dict = None) -> dict:
    """
    Stub para la extracción de Estados Financieros Dictaminados.
    Por ahora, devuelve la misma estructura base que extract_tables_from_pages
    para que la UI no falle.
    """
    logger.info(f"Extracting dictaminado from {pdf_path} for pages {target_pages}")
    
    # Return empty/mock structure matching the expected format
    results = []
    for p_num in target_pages:
        page_result = {
            "page_num": p_num,
            "method": "dictaminado_stub",
            "tables": [],  # Empty tables for now until extraction is implemented
            "page_width": 600,
            "page_height": 800
        }
        results.append(page_result)
        
    return {"pages": results, "year": "Desconocido"}
