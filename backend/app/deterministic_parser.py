"""
Deterministic Financial PDF Parser v3.
Extracts financial data directly from PDF using pdfplumber.

KEY DESIGN DECISIONS:
- Balance General: Uses ANALITICAS pages (cleanest numbers, detailed breakdown)
- Estado de Resultados: Uses the FORMAL EDO page (page 2) because it has
  pre-calculated "Total" lines (Total Costos = bruto - devoluciones, etc.)
- Capital: Searches across balance page AND analiticas (some fields only appear in one)
- Gastos/Productos Financieros: Uses the HEADER values (already include sub-items
  like pérdida cambiaria, comisiones, utilidad cambiaria)
- utilidad_perdida_cambiaria: ALWAYS 0 (already included in gastos/productos financieros)
- otros_gastos: Only extracted if there's a standalone "Otros Gastos" section,
  NOT "otros gastos generales" (which is a sub-item of Gastos generales)
"""
import re
import logging
import pdfplumber
from pathlib import Path

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# NUMBER PARSING (OCR-tolerant)
# ══════════════════════════════════════════════════════════════════

def _parse_number(raw: str) -> float:
    """
    Parse a financial number from PDF text, handling OCR artifacts.
    
    Real examples from our PDFs:
      '25,934.63'        -> 25934.63
      '17,934.O1'        -> 17934.01    (O is letter, not zero)
      '3,354,211.19'     -> 3354211.19
      '3 300,682 42'     -> 3300682.42  (spaces instead of commas/dots)
      '-19,331 .91'      -> -19331.91   (space before decimal)
      '-124,435.18'      -> -124435.18  (negative)
      '-124,435.'lg'     -> -124435.18  (OCR junk after number)
      '1 ,5A2,444 .51'   -> 1502444.51  (OCR mess)
      '309,3'10.34'      -> 309310.34   (backslash artifact)
    """
    if not raw:
        return 0.0
    
    text = raw.strip()
    
    # Detect negative
    negative = False
    if text.startswith('-') or text.startswith('('):
        negative = True
        text = text.lstrip('-( ').rstrip(') ')
    
    # Remove currency symbols
    text = re.sub(r'[$€£¥]', '', text)
    
    # Fix OCR artifacts
    text = text.replace("\\", "").replace("'", "")
    
    # Fix letter→digit in numeric context: A→0, O→0, l→1
    text = re.sub(r'(?<=\d)[A-Za-z](?=\d)', '0', text)
    text = re.sub(r'(?<=[\d,.])[Oo](?=\d)', '0', text)
    text = re.sub(r'(?<=\d)[Oo](?=[\d,.])', '0', text)
    
    # Remove trailing non-numeric junk (e.g., "'lg" from OCR)
    text = re.sub(r'[^0-9,.\s-]+$', '', text)
    
    # Split by spaces and reassemble
    parts = text.split()
    
    if len(parts) == 1:
        clean = parts[0]
    else:
        reassembled = ''.join(parts)
        
        if reassembled.count('.') == 1:
            clean = reassembled
        elif reassembled.count('.') == 0:
            # No dots: check if last part is 2 digits (likely decimals)
            if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isdigit():
                clean = ''.join(parts[:-1]) + '.' + parts[-1]
            else:
                clean = reassembled
        else:
            # Multiple dots: last dot is decimal separator
            last_dot = reassembled.rfind('.')
            after_last_dot = reassembled[last_dot+1:]
            digits_after = re.sub(r'[^\d]', '', after_last_dot)
            if len(digits_after) <= 2:
                before = reassembled[:last_dot].replace('.', '').replace(',', '')
                clean = before + '.' + digits_after
            else:
                clean = reassembled.replace('.', '')
    
    # Parse: determine decimal separator
    dots = clean.count('.')
    commas = clean.count(',')
    
    if dots == 1 and commas >= 0:
        clean = clean.replace(',', '')
    elif dots == 0 and commas == 1:
        clean = clean.replace(',', '.')
    elif dots == 0 and commas == 0:
        pass
    elif dots > 1:
        if commas == 1:
            clean = clean.replace('.', '').replace(',', '.')
        else:
            clean = clean.replace('.', '')
    
    # Final cleanup
    clean = re.sub(r'[^\d.]', '', clean)
    if clean.count('.') > 1:
        parts = clean.split('.')
        clean = ''.join(parts[:-1]) + '.' + parts[-1]
    
    if not clean:
        return 0.0
    
    try:
        value = float(clean)
        return -value if negative else value
    except ValueError:
        return 0.0


def _extract_all_numbers_from_line(line: str) -> list[float]:
    """Extract all numeric values from a line, left to right."""
    candidates = re.findall(r'-?(?:\d[\d,.\s\\\'OoAa]*\d|\d)', line)
    results = []
    for c in candidates:
        c = c.strip()
        if len(re.sub(r'[^\d]', '', c)) < 2:
            continue
        val = _parse_number(c)
        if val != 0 or '0' in c:
            results.append(val)
    return results


def _get_rightmost_number(line: str) -> float | None:
    """Get the rightmost (usually the value) number from a line."""
    numbers = _extract_all_numbers_from_line(line)
    return numbers[-1] if numbers else None


# ══════════════════════════════════════════════════════════════════
# TEXT NORMALIZATION (OCR-tolerant)
# ══════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """Normalize text for keyword matching, handling OCR artifacts."""
    t = text.lower()
    t = t.replace('í', 'i').replace('ó', 'o').replace('á', 'a')
    t = t.replace('é', 'e').replace('ú', 'u').replace('ñ', 'n')
    t = t.replace('ï', 'i').replace('ö', 'o').replace('ä', 'a')
    # Fix OCR: lowercase L at start of word often means uppercase I
    t = re.sub(r'\bl(?=[mnpqrstvwy])', 'i', t)
    t = t.replace('lva', 'iva')
    return t


# ══════════════════════════════════════════════════════════════════
# KEYWORD MAPS
# ══════════════════════════════════════════════════════════════════

BALANCE_MAP = {
    # Activo Circulante
    "caja": ["caja y efectivo", "caja"],
    "bancos": ["bancos nacionales", "bancos"],
    "clientes": ["clientes nacionales", "clientes"],
    "cuentas_por_cobrar": ["cuentas por cobrar"],
    "deudores_diversos": ["deudores diversos", "otros deudores"],
    "isr_diferido": ["isr diferido"],
    "inventarios": ["inventarios", "almacen"],
    "pagos_anticipados": ["pagos anticipados"],
    "anticipo_proveedores": ["anticipo a proveedores", "anticipo proveedores"],
    
    # Activo Fijo
    "edificios": ["edificios", "inmuebles"],
    "maquinaria_equipo": ["maquinaria y equipo", "maquinaria"],
    "equipo_transporte": ["equipo de transporte", "automoviles, autobuses", "automoviles"],
    "mobiliario_equipo": ["mobiliario y equipo", "mobiliario"],
    "equipo_computo": ["equipo de computo", "equipo computo"],
    "otros_activos_fijos": ["otros activos fijos"],
    "terrenos": ["terrenos"],
    "depreciacion_acumulada": ["depreciacion acumulada"],
    
    # Activo Diferido
    "gastos_instalacion": ["gastos de instalacion", "gastos instalacion"],
    "depositos_garantia": ["depositos en garantia", "depositos garantia"],
    "otros_activos_largo_plazo": ["otros activos diferidos"],
    
    # Pasivo Corto Plazo
    "proveedores": ["proveedores nacionales", "proveedores"],
    "prestamos_bancarios_cp": ["prestamos bancarios"],
    "acreedores_diversos": ["acreedores diversos"],
    "otros_pasivos_cp": ["otros pasivos"],
    "anticipo_clientes": ["anticipo de clientes", "anticipo clientes"],
    
    # Pasivo Largo Plazo
    "prestamos_bancarios_lp": ["prestamos bancarios a largo"],
    "otras_cuentas_lp": ["otras cuentas largo plazo"],
    
    # Capital
    "capital_social": ["capital social", "capital fijo"],
    "reserva_legal": ["reserva legal"],
    "aportaciones_futuros_aumentos": ["aportaciones para futuros", "aportaciones futuros"],
    "resultados_ejercicios_anteriores": [
        "resultado de ejercicios anteriores",
        "resultados de ejercicios anteriores",
        "perdida de ejercicios anteriores",
        "utilidades acumuladas",
        "resultados acumulados",
    ],
    "utilidad_ejercicio": [
        "utilidad o perdida del ejercicio",
        "utilidad del ejercicio",
        "resultado del ejercicio",
        "utilidad neta",
        "perdida neta",
    ],
}

# Keys where we look for the HEADER/PARENT value (the totaled line, not sub-items)
BALANCE_HEADER_KEYS = {
    "caja", "bancos", "clientes", "deudores_diversos",
    "proveedores", "acreedores_diversos", "depreciacion_acumulada",
    "equipo_transporte", "capital_social",
}

# ── Estado de Resultados ──
# IMPORTANT: We use the Edo de Resultados PAGE (page 2), NOT analiticas for this.
# Page 2 has pre-calculated "Total" lines that are already NET of devoluciones.
# The keyword search uses "Total X" lines for ventas, costos, gastos.
EDO_TOTAL_KEYWORDS = {
    # key: [keywords] - searched in header_mode (must be at start of line)
    # Includes both "Total X" (from Edo page) and bare "X" (from analiticas)
    "ventas": ["total ingresos", "ingresos"],
    "costo_ventas": ["total costos", "costos"],
    "gastos_generales": ["total gastos", "gastos"],
}

EDO_LINE_KEYWORDS = {
    # key: [keywords for individual lines]
    "gastos_administracion": ["gastos de administracion", "gastos administracion"],
    "gastos_financieros": ["gastos financieros"],        # HEADER value (includes all sub-items)
    "productos_financieros": ["productos financieros"],   # HEADER value (includes all sub-items)
    "depreciacion": ["depreciacion contable"],
    "impuestos": ["impuestos a la utilidad", "isr del ejercicio", "impuesto sobre la renta"],
    # otros_gastos: Only if there's a standalone "Otros Gastos" or "Otros Egresos" section
    # NOT "otros gastos generales" (which is a sub-item of Gastos generales)
    "otros_gastos": ["otros egresos", "otros gastos no operativos"],
    "otros_ingresos": ["otros ingresos", "otros productos"],
}

# Fields that are ALWAYS 0 because they're already included in other fields
EDO_ALWAYS_ZERO = {
    "utilidad_perdida_cambiaria",  # Already in gastos_financieros / productos_financieros
}


# ══════════════════════════════════════════════════════════════════
# SEARCH FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _find_value(lines: list[str], keywords: list[str], header_mode: bool = False) -> float:
    """
    Find a value in the lines by keyword.
    header_mode: match only if keyword is at line start and not part of a longer word.
    """
    for kw in keywords:
        kw_norm = _normalize(kw)
        for line in lines:
            line_norm = _normalize(line)
            if kw_norm not in line_norm:
                continue
            if header_mode:
                stripped = line_norm.strip()
                if not stripped.startswith(kw_norm):
                    continue
                after = stripped[len(kw_norm):]
                if after and after[0].isalpha():
                    continue
            val = _get_rightmost_number(line)
            if val is not None:
                return val
    return 0.0


def _find_total_line(lines: list[str], keywords: list[str]) -> float:
    """
    Find a "Total X" line. These are the pre-calculated totals on the Edo page.
    Example: "Total Costos 19,898,666.94" (already net of devoluciones)
    """
    for kw in keywords:
        kw_norm = _normalize(kw)
        for line in lines:
            line_norm = _normalize(line)
            if kw_norm in line_norm:
                val = _get_rightmost_number(line)
                if val is not None and val != 0:
                    return val
    return 0.0


def _find_year_in_text(full_text: str) -> str | None:
    """Try to find the fiscal year from the document text."""
    match = re.search(
        r'(?:al\s+\d+\s+de\s+\w+\s+de\s+|ejercicio\s+|a[nñ]o\s+)(\d{4})',
        full_text, re.IGNORECASE
    )
    if match:
        return match.group(1)
    years = re.findall(r'\b(20[2-3]\d)\b', full_text)
    return years[0] if years else None


def _find_total_pasivo_cp(lines: list[str]) -> float:
    """Find 'Total Pasivo a corto plazo'."""
    for line in lines:
        norm = _normalize(line)
        if "total pasiv" in norm and ("corto" in norm or "carto" in norm):
            val = _get_rightmost_number(line)
            if val is not None and val > 0:
                return val
    return 0.0


def _sum_impuestos_a_favor(lines: list[str]) -> float:
    """Sum all tax-credit accounts."""
    total = 0.0
    keywords = [
        "impuestos a favor",
        "impuestos acreditables",
        "isr a favor",
        "subsidio al empleo",
    ]
    matched = set()
    for kw in keywords:
        kw_norm = _normalize(kw)
        for i, line in enumerate(lines):
            if i in matched:
                continue
            if kw_norm in _normalize(line):
                val = _get_rightmost_number(line)
                if val is not None and abs(val) > 0:
                    total += abs(val)
                    matched.add(i)
                    break
    return total


# ══════════════════════════════════════════════════════════════════
# MAIN PARSER
# ══════════════════════════════════════════════════════════════════

def parse_financial_pdf(pdf_path: str | Path) -> dict:
    """
    Parse a financial PDF and extract structured data deterministically.
    
    Strategy:
    - Balance General: Analiticas pages (detailed, clean numbers)
    - Estado de Resultados: Formal Edo page (pre-calculated totals)
    - Capital: Both balance page and analiticas (fields may appear in either)
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        return {"success": False, "error": f"PDF not found: {pdf_path}"}
    
    try:
        all_lines = []
        pages_lines = {}
        page_sections = {}
        
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                lines = text.strip().split("\n")
                pages_lines[i] = lines
                all_lines.extend(lines)
                
                text_lower = text.lower()
                if "balance general" in text_lower or "situacion financiera" in text_lower:
                    page_sections[i] = "balance"
                elif "estado de resultados" in text_lower:
                    page_sections[i] = "edo_resultados"
                elif "analiticas" in text_lower or "auxiliar" in text_lower:
                    page_sections[i] = "analiticas"
        
        # Build section line groups
        balance_lines = []
        edo_lines = []
        analiticas_lines = []
        
        current_section = None
        for i in sorted(pages_lines.keys()):
            if i in page_sections:
                current_section = page_sections[i]
            
            if current_section == "balance":
                balance_lines.extend(pages_lines[i])
            elif current_section == "edo_resultados":
                edo_lines.extend(pages_lines[i])
            elif current_section == "analiticas":
                analiticas_lines.extend(pages_lines[i])
        
        year = _find_year_in_text("\n".join(all_lines[:20])) or "2024"
        logger.info(f"Parser v3: year={year}, pages={len(pages_lines)}, "
                     f"balance={len(balance_lines)}, edo={len(edo_lines)}, "
                     f"analiticas={len(analiticas_lines)}")
        
        # ── SOURCE SELECTION ──
        # Balance: analiticas first, balance page fallback
        bal_source = analiticas_lines if analiticas_lines else balance_lines
        if not bal_source:
            bal_source = all_lines
        
        # Edo Resultados: Try BOTH sources and cross-validate
        # Analiticas headers are cleaner (no OCR mess), but Edo page has "Total" lines
        # Strategy: try analiticas first, then edo, pick the most reliable
        edo_primary = analiticas_lines if analiticas_lines else edo_lines
        edo_fallback = edo_lines if analiticas_lines else all_lines
        if not edo_primary:
            edo_primary = all_lines
        if not edo_fallback:
            edo_fallback = all_lines
        
        # Capital: search balance page + analiticas (fields appear in different places)
        capital_source = balance_lines + analiticas_lines
        if not capital_source:
            capital_source = all_lines
        
        # ══════════════════════════════════════════════════════
        # EXTRACT BALANCE GENERAL
        # ══════════════════════════════════════════════════════
        balance_data = {}
        
        for key, keywords in BALANCE_MAP.items():
            if key in ("resultados_ejercicios_anteriores", "utilidad_ejercicio"):
                continue  # Handle separately (sign matters)
            
            is_header = key in BALANCE_HEADER_KEYS
            val = _find_value(bal_source, keywords, header_mode=is_header)
            balance_data[key] = abs(val)
        
        # ── Capital fields that keep their sign ──
        # Search capital_source (balance page + analiticas combined)
        for key in ("resultados_ejercicios_anteriores", "utilidad_ejercicio"):
            keywords = BALANCE_MAP[key]
            val = _find_value(capital_source, keywords, header_mode=False)
            # These can be negative (loss)
            balance_data[key] = val
            logger.info(f"  Capital field {key} = {val}")
        
        # ── impuestos_a_favor = sum of sub-accounts ──
        balance_data["impuestos_a_favor"] = _sum_impuestos_a_favor(bal_source)
        
        # ── impuestos_acumulados = Total Pasivo CP - known categories ──
        total_pasivo_cp = _find_total_pasivo_cp(
            balance_lines if balance_lines else all_lines
        )
        known_pasivo = sum(
            balance_data.get(k, 0) for k in [
                "proveedores", "acreedores_diversos",
                "prestamos_bancarios_cp", "anticipo_clientes", "otros_pasivos_cp"
            ]
        )
        balance_data["impuestos_acumulados"] = max(0, total_pasivo_cp - known_pasivo)
        
        # ══════════════════════════════════════════════════════
        # EXTRACT ESTADO DE RESULTADOS
        # ══════════════════════════════════════════════════════
        edo_data = {}
        
        # 1. Extract "Total" lines - try analiticas headers first (cleanest)
        #    then fall back to edo page "Total X" lines
        for key, keywords in EDO_TOTAL_KEYWORDS.items():
            # Try analiticas first (header mode: "Costos 10,577,379.41")
            val = _find_value(edo_primary, keywords, header_mode=True)
            if val == 0:
                # Fallback: look for "Total X" on the Edo page
                val = _find_total_line(edo_fallback, keywords)
            if val == 0:
                # Last resort: try without header mode
                val = _find_value(edo_primary, keywords, header_mode=False)
            edo_data[key] = abs(val)
            logger.info(f"  Edo Total: {key} = {val}")
        
        # 2. Extract individual line items (gastos_financieros, productos_financieros, etc.)
        for key, keywords in EDO_LINE_KEYWORDS.items():
            # Try analiticas first, then edo page
            val = _find_value(edo_primary, keywords, header_mode=False)
            if val == 0:
                val = _find_value(edo_fallback, keywords, header_mode=False)
            edo_data[key] = abs(val)
        
        # 3. Set always-zero fields
        for key in EDO_ALWAYS_ZERO:
            edo_data[key] = 0.0
        
        # ── Build result ──
        result_data = {
            "tipo_documento": "caf_brightec",
            "Balance": {year: balance_data},
            "Edo de resultados": {year: edo_data},
        }
        
        # Log summary
        nonzero_bal = {k: v for k, v in balance_data.items() if v != 0}
        nonzero_edo = {k: v for k, v in edo_data.items() if v != 0}
        logger.info(f"Balance ({len(nonzero_bal)} fields): {nonzero_bal}")
        logger.info(f"Edo Resultados ({len(nonzero_edo)} fields): {nonzero_edo}")
        
        return {
            "success": True,
            "document_type": "caf_brightec",
            "data": result_data,
            "method": "deterministic_parser_v3",
            "raw_response": f"Parsed {len(all_lines)} lines from {pdf_path.name}",
        }
        
    except Exception as e:
        logger.error(f"Deterministic parser failed: {e}", exc_info=True)
        return {"success": False, "error": f"Deterministic parser failed: {str(e)}"}
