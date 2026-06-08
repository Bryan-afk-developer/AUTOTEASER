"""
mop_extractor.py — Extrae el Histórico de Pagos (MOPs) de un reporte de
Buró de Crédito Personas Morales en formato PDF.

Lógica:
  - Descarga el PDF de Supabase Storage
  - Usa pdfplumber para extraer palabras con posiciones
  - Agrupa palabras por línea (y-coordinate)
  - Detecta líneas que contienen un año (ej: 2023) + dígitos MOP (1-7)
  - Cuenta ocurrencias de cada nivel (1-7) por año
  - Devuelve estructura tabular + flag de alerta (nivel ≥ 3)

MOP Scale (Buró de Crédito Personas Morales):
  1 = Al corriente
  2 = Atraso 1-29 días      ← detectar, sin alerta
  3 = Atraso 30-59 días     ← alerta
  4 = Atraso 60-89 días     ← alerta
  5 = Atraso 90-119 días    ← alerta
  6 = Atraso 120-179 días   ← alerta
  7 = Atraso 180+ días      ← alerta máxima
"""
import io
import logging
import re
from collections import defaultdict

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Niveles que disparan alerta visual
ALERTA_DESDE = 3
# Niveles que se detectan (se muestran en tabla aunque no alerten)
DETECTAR_DESDE = 2
# Todos los niveles posibles
ALL_NIVELES = [1, 2, 3, 4, 5, 6, 7]
# Años válidos para el reporte (desde 2018 en adelante)
YEAR_MIN = 2018
YEAR_MAX = 2030

MOP_VALID = {'1', '2', '3', '4', '5', '6', '7'}


def _is_valid_year(text: str) -> bool:
    """Verifica si el texto es un año razonable para un reporte de Buró."""
    if not re.match(r'^20[12][0-9]$', text):
        return False
    year = int(text)
    return YEAR_MIN <= year <= YEAR_MAX


def extraer_mops_de_bytes(pdf_bytes: bytes) -> dict:
    """
    Extrae los MOPs de los bytes de un PDF de Buró de Crédito.

    Returns:
        {
          "mops_detectados": bool,
          "alerta": bool,
          "años": [2023, 2024, 2025],          # años encontrados, ordenados desc
          "niveles": {
              1: {"2023": 10, "2024": 21},     # solo años con datos
              2: {"2023": 4},
              ...
          },
          "mops_alerta": [                      # niveles ≥ 3 con conteos
              {"nivel": 3, "año": "2023", "conteo": 2},
              ...
          ]
        }
    """
    mops_por_nivel: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text() or ''

            # Solo procesar páginas con contenido de créditos/pagos
            keywords = ['Hist', 'Pago', 'CREDITO', 'CRÉDITO', 'Crédito', 'Mes E F']
            if not any(kw in text for kw in keywords):
                continue

            try:
                words = page.get_text("words") # list of tuples: (x0, y0, x1, y1, word, block_no, line_no, word_no)
            except Exception as e:
                logger.warning(f"Error extrayendo palabras de página: {e}")
                continue

            # Agrupar palabras por línea (y-position redondeada a múltiplos de 4)
            lines: dict[int, list] = defaultdict(list)
            for w in words:
                y_key = round(float(w[1]) / 4) * 4
                lines[y_key].append(w)

            # Analizar cada línea buscando patrón: AÑO + dígitos MOP
            for y_key in sorted(lines.keys()):
                line_words = sorted(lines[y_key], key=lambda w: w[0])
                year_words = [w for w in line_words if _is_valid_year(w[4])]

                if year_words:
                    year_word = year_words[0]
                    year_text = year_word[4]
                    year_x = year_word[0]
                    
                    # Los verdaderos dígitos MOP en la tabla de Histórico siempre 
                    # aparecen a la DERECHA del año. Esto evita falsos positivos 
                    # con otros campos numéricos (como Plazo o Frecuencia) que caen a la izquierda.
                    mop_words = [w for w in line_words if w[4] in MOP_VALID and w[0] > year_x]
                    
                    for w in mop_words:
                        nivel = int(w[4])
                        mops_por_nivel[nivel][year_text] += 1

    # --- Construir respuesta estructurada ---
    años_set: set[str] = set()
    for nivel_data in mops_por_nivel.values():
        años_set.update(nivel_data.keys())

    años_ordenados: list[str] = sorted(años_set, reverse=True)  # más reciente primero

    mops_alerta = []
    for nivel in sorted(mops_por_nivel.keys()):
        if nivel >= ALERTA_DESDE:
            for año, conteo in sorted(mops_por_nivel[nivel].items(), reverse=True):
                mops_alerta.append({"nivel": nivel, "anio": año, "conteo": conteo})

    tiene_mops_detectados = any(
        nivel >= DETECTAR_DESDE for nivel in mops_por_nivel.keys()
    )
    tiene_alerta = len(mops_alerta) > 0

    # Convertir defaultdict a dict normal para serialización
    niveles_resultado: dict[str, dict[str, int]] = {}
    for nivel in ALL_NIVELES:
        if nivel in mops_por_nivel:
            niveles_resultado[str(nivel)] = dict(mops_por_nivel[nivel])

    return {
        "mops_detectados": tiene_mops_detectados,
        "alerta": tiene_alerta,
        "anios": años_ordenados,
        "niveles": niveles_resultado,
        "mops_alerta": mops_alerta,
        "total_mops_nivel2_plus": sum(
            sum(v.values()) for k, v in mops_por_nivel.items() if k >= DETECTAR_DESDE
        ),
    }


def extraer_mops_desde_storage(storage_path: str, supabase_client) -> dict:
    """
    Descarga el PDF de Buró de Crédito desde Supabase Storage y extrae los MOPs.

    Args:
        storage_path: Ruta del archivo en el bucket de Supabase.
        supabase_client: Cliente de Supabase con permisos de admin.

    Returns:
        Diccionario con los MOPs detectados (ver extraer_mops_de_bytes).
    """
    try:
        pdf_bytes = supabase_client.storage.from_("expedientes_clientes").download(storage_path)
    except Exception as e:
        logger.error(f"Error descargando PDF de Buró de Crédito desde Storage ({storage_path}): {e}")
        return {
            "error": f"No se pudo descargar el PDF: {e}",
            "mops_detectados": False,
            "alerta": False,
            "años": [],
            "niveles": {},
            "mops_alerta": [],
            "total_mops_nivel2_plus": 0,
        }

    try:
        return extraer_mops_de_bytes(pdf_bytes)
    except Exception as e:
        logger.error(f"Error extrayendo MOPs del PDF ({storage_path}): {e}")
        return {
            "error": f"No se pudo analizar el PDF: {e}",
            "mops_detectados": False,
            "alerta": False,
            "años": [],
            "niveles": {},
            "mops_alerta": [],
            "total_mops_nivel2_plus": 0,
        }
