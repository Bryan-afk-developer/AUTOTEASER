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
ALL_NIVELES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
# Años válidos para el reporte (desde 2018 en adelante)
YEAR_MIN = 2018
YEAR_MAX = 2030

MOP_VALID = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}


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
    extracted_rfc = None

    all_pages_text = ""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text() or ''
            all_pages_text += text + "\n"
            
            # Buscar RFC en cualquier página (usualmente está en la primera)
            if not extracted_rfc:
                rfc_match = re.search(r'([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})', text)
                if rfc_match:
                    extracted_rfc = rfc_match.group(1)

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

    # Extraer detalle de cuentas
    cuentas = extraer_cuentas_de_detalle(all_pages_text)

    return {
        "mops_detectados": tiene_mops_detectados,
        "alerta": tiene_alerta,
        "rfc": extracted_rfc,
        "anios": años_ordenados,
        "niveles": niveles_resultado,
        "mops_alerta": mops_alerta,
        "total_mops_nivel2_plus": sum(
            sum(v.values()) for k, v in mops_por_nivel.items() if k >= DETECTAR_DESDE
        ),
        "cuentas": cuentas,
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
            "cuentas": [],
        }


HEADER_PATTERNS = [
    r'Reporte de Cr\u00e9dito Especial',
    r'Folio de Consulta',
    r'Personas Morales',
    r'^-$',
    r'^\d{9,12}$',
    r'DETALLE DE CR\u00c9DITOS',
    r'Todas las cantidades del Reporte',
    r'^CR\u00c9DITOS FINANCIEROS$',
    r'^CR\u00c9DITOS COMERCIALES$',
    r'Otorgante / No\.',
    r'Tipo de Cr\u00e9dito',
    r'Hist\u00f3rico de Pagos',
    r'Clave de Observaci\u00f3n',
    r'Saldo\s*Vencido',
    r'Saldo\s*Actual',
    r'Cr\u00e9dito\s*Otorgado',
    r'Moneda',
    r'Plazo',
    r'Apertura',
    r'Actualizado',
    r'D\u00edas de Atraso',
    r'D\u00edas de\s*Atraso',
    r'Quebranto',
    r'Pago',
    r'Daci\u00f3n',
    r'Quita',
    r'Fecha\s*de Cierre',
    r'P\u00c1GINA \d+ DE \d+',
    r'DOCUMENTO SIN VALOR PROBATORIO',
    r'^D\u00edas de$',
    r'^Atraso$',
    r'^Saldo$',
    r'^Vencido$',
    r'^Actual$',
    r'^Fecha$',
    r'^de Cierre$',
    r'^Cierre$',
    r'^Cr\u00e9dito$',
    r'^Otorgado$',
    r'^Quebranto$',
    r'^Pago$',
    r'^Daci\u00f3n$',
    r'^Quita$',
    r'^Fecha\s*de Cierre$',
    r'^P\u00c1GINA \d+ DE \d+$'
]

def _clean_text_lines(text):
    lines = text.split("\n")
    cleaned = []
    seen_sections = set()
    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
            
        is_section_header = False
        for sec in ["FINANCIEROS ACTIVOS", "FINANCIEROS LIQUIDADOS", "FINANCIEROS CERRADOS", "COMERCIALES"]:
            if sec in line_s:
                is_section_header = True
                if sec not in seen_sections:
                    seen_sections.add(sec)
                    cleaned.append(sec) # Use the exact string to standardize
                break
                
        if is_section_header:
            continue
            
        is_header = False
        for pat in HEADER_PATTERNS:
            if re.search(pat, line_s, re.IGNORECASE):
                is_header = True
                break
        if not is_header:
            cleaned.append(line_s)
    return "\n".join(cleaned)

def _parse_amount(text):
    if not text:
        return 0.0
    val = text.replace(",", "").strip()
    try:
        return float(val)
    except:
        return 0.0

def _is_number(text):
    return bool(re.match(r'^\d+([.,]\d+)*$', text))

def _parse_financial_credits(text, section_type, section_header):
    raw_blocks = re.split(r'\n\d+\.\n', text)
    items_raw = []
    
    first_block = raw_blocks[0]
    pos = first_block.find(section_header)
    if pos != -1:
        first_item_text = first_block[pos + len(section_header):].strip()
        items_raw.append(first_item_text)
    else:
        items_raw.append(first_block.strip())
            
    for block in raw_blocks[1:]:
        items_raw.append(block.strip())
        
    credits = []
    for idx, item_text in enumerate(items_raw):
        lines = [l.strip() for l in item_text.split("\n") if l.strip()]
        if not lines:
            continue
            
        start_idx = 0
        if section_type == "CERRADOS" and idx > 0:
            if len(lines) > 2 and _is_number(lines[0]) and _is_number(lines[1]) and not _is_number(lines[2]):
                start_idx = 2
            elif len(lines) > 1 and _is_number(lines[0]) and not _is_number(lines[1]):
                start_idx = 1
                
        item_lines = lines[start_idx:]
        if len(item_lines) < 8:
            continue
            
        otorgante = item_lines[0]
        contrato = item_lines[1]
        tipo_credito = item_lines[2]
        
        current_idx = 3
        responsabilidad = "Titular"
        if not _is_number(item_lines[current_idx]):
            responsabilidad = item_lines[current_idx]
            current_idx += 1
            
        try:
            if section_type == "ACTIVOS":
                saldo_vencido = _parse_amount(item_lines[current_idx])
                saldo_actual = _parse_amount(item_lines[current_idx+1])
                credito_otorgado = _parse_amount(item_lines[current_idx+2])
                moneda = item_lines[current_idx+3]
                
                current_idx += 4
                if item_lines[current_idx].startswith("$"):
                    current_idx += 1
                    
                plazo = int(_parse_amount(item_lines[current_idx]))
                apertura = item_lines[current_idx+1]
                actualizado = item_lines[current_idx+2]
                dias_atraso = int(_parse_amount(item_lines[current_idx+3]))
                
                credits.append({
                    "otorgante": otorgante,
                    "contrato": contrato,
                    "tipo_credito": tipo_credito,
                    "responsabilidad": responsabilidad,
                    "saldo_vencido": saldo_vencido,
                    "saldo_actual": saldo_actual,
                    "limite_credito": credito_otorgado,
                    "moneda": moneda,
                    "plazo": plazo,
                    "apertura": apertura,
                    "actualizado": actualizado,
                    "dias_atraso": dias_atraso,
                    "estado": "ACTIVO"
                })
            else:
                saldo_vencido = _parse_amount(item_lines[current_idx])
                saldo_actual = _parse_amount(item_lines[current_idx+1])
                dacion = _parse_amount(item_lines[current_idx+2])
                quita = _parse_amount(item_lines[current_idx+3])
                fecha_cierre = item_lines[current_idx+4]
                moneda = item_lines[current_idx+5]
                
                current_idx += 6
                if item_lines[current_idx].startswith("$"):
                    current_idx += 1
                    
                actualizado = item_lines[current_idx]
                dias_atraso = int(_parse_amount(item_lines[current_idx+1]))
                
                credits.append({
                    "otorgante": otorgante,
                    "contrato": contrato,
                    "tipo_credito": tipo_credito,
                    "responsabilidad": responsabilidad,
                    "saldo_vencido": saldo_vencido,
                    "saldo_actual": saldo_actual,
                    "dacion": dacion,
                    "quita": quita,
                    "fecha_cierre": fecha_cierre,
                    "moneda": moneda,
                    "actualizado": actualizado,
                    "dias_atraso": dias_atraso,
                    "estado": "CERRADO"
                })
        except Exception as e:
            logger.warning(f"Error parsing credit item: {e}")
            
    return credits


def _parse_personal_credits(text: str) -> list:
    """
    Parsea créditos de Buró de Crédito Personas Físicas (representantes legales).
    Formato: créditos numerados con 1., 2., etc.
    """
    credits = []
    # Separar por numeración: "1.\n", "2.\n", etc.
    # El primer bloque es el encabezado, los siguientes son créditos
    blocks = re.split(r'\n\d+\.\n', text)
    
    for block in blocks[1:]:  # Skip header block
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if len(lines) < 4:
            continue

        try:
            # Estructura típica del formato personal:
            # [0] Otorgante (banco)
            # [1] No. de cuenta/contrato
            # [2] Tipo de crédito
            # [3] Responsabilidad (INDIVIDUAL, etc.) - a veces está separado
            # Luego: saldo_actual, credito_maximo, limite_credito, moneda, fecha_cierre, ...
            
            otorgante = lines[0]
            contrato = lines[1]
            tipo_credito = lines[2]
            
            idx = 3
            responsabilidad = "INDIVIDUAL"
            if idx < len(lines) and not _is_number(lines[idx]) and not re.match(r'^[A-Z]{2,3}$', lines[idx]):
                responsabilidad = lines[idx]
                idx += 1
            
            def _amt(s):
                return _parse_amount(s.replace('$', '').strip())
            
            saldo_actual = _amt(lines[idx]) if idx < len(lines) else 0
            credito_maximo = _amt(lines[idx+1]) if idx+1 < len(lines) else 0
            limite_credito = _amt(lines[idx+2]) if idx+2 < len(lines) else 0
            
            # Buscar moneda (MX, USD, etc.) y fechas
            moneda = "MX"
            fecha_cierre = ""
            apertura = ""
            for i in range(idx+3, min(idx+10, len(lines))):
                val = lines[i].strip()
                if re.match(r'^(MX|USD|EUR|UDIS)$', val, re.IGNORECASE):
                    moneda = val
                elif re.match(r'^[A-Z]{3}-\d{2}$', val):  # ej: MAR-26
                    if not fecha_cierre:
                        fecha_cierre = val
                    else:
                        apertura = val
            
            credits.append({
                "otorgante": otorgante,
                "contrato": contrato,
                "tipo_credito": tipo_credito,
                "responsabilidad": responsabilidad,
                "saldo_actual": saldo_actual,
                "limite_credito": max(credito_maximo, limite_credito),
                "saldo_vencido": 0,
                "moneda": moneda,
                "apertura": apertura,
                "fecha_cierre": fecha_cierre,
                "dias_atraso": 0,
                "estado": "ACTIVO" if not fecha_cierre or int(fecha_cierre[-2:]) >= 24 else "CERRADO"
            })
        except Exception as e:
            logger.debug(f"Error parsing personal credit block: {e}")
            continue
    
    return credits


def extraer_cuentas_de_detalle(all_text):
    match = re.search(r'DETALLE DE CR.DITOS?', all_text, re.IGNORECASE)
    if not match:
        return []
        
    detalle_text = all_text[match.start():]
    cleaned_detalle = _clean_text_lines(detalle_text)
    
    # ── Personas Morales: secciones "FINANCIEROS ACTIVOS", etc. ──────────────
    subsecciones_morales = [
        "FINANCIEROS ACTIVOS",
        "FINANCIEROS LIQUIDADOS",
        "FINANCIEROS CERRADOS",
        "COMERCIALES"
    ]
    
    posiciones = []
    for sub in subsecciones_morales:
        pos = cleaned_detalle.find(sub)
        if pos != -1:
            posiciones.append((pos, sub))
    posiciones.sort()
    
    if posiciones:
        secciones_dict = {}
        for i in range(len(posiciones)):
            pos, sub = posiciones[i]
            fin = posiciones[i+1][0] if i+1 < len(posiciones) else len(cleaned_detalle)
            secciones_dict[sub] = cleaned_detalle[pos:fin]
            
        cuentas = []
        if "FINANCIEROS ACTIVOS" in secciones_dict:
            cuentas.extend(_parse_financial_credits(secciones_dict["FINANCIEROS ACTIVOS"], "ACTIVOS", "FINANCIEROS ACTIVOS"))
        if "FINANCIEROS LIQUIDADOS" in secciones_dict:
            cuentas.extend(_parse_financial_credits(secciones_dict["FINANCIEROS LIQUIDADOS"], "CERRADOS", "FINANCIEROS LIQUIDADOS"))
        elif "FINANCIEROS CERRADOS" in secciones_dict:
            cuentas.extend(_parse_financial_credits(secciones_dict["FINANCIEROS CERRADOS"], "CERRADOS", "FINANCIEROS CERRADOS"))
        return cuentas
    
    # ── Personas Físicas: secciones "CRÉDITOS BANCARIOS", etc. ──────────────
    # Detectar si es formato personal buscando BANCARIOS o créditos numerados
    if "BANCARIOS" in cleaned_detalle or re.search(r'\n1\.\n', cleaned_detalle):
        return _parse_personal_credits(cleaned_detalle)
    
    return []
