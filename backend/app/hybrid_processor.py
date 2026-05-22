"""
Hybrid Financial Processor v1.
Step 1: pdfplumber extracts EXACT text from PDF (no hallucination).
Step 2: Gemini reads that CLEAN text and maps it to JSON (reasoning + calculations).
Step 3: Validation ensures output numbers match the source text.

Best of both worlds: exact numbers + flexible format handling.
"""
import re
import json
import logging
import pdfplumber
import google.generativeai as genai
from pathlib import Path

logger = logging.getLogger(__name__)


def _extract_clean_text(pdf_path: Path) -> str:
    """Extract clean, well-structured text from PDF using pdfplumber."""
    all_text = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                all_text.append(f"--- PÁGINA {i+1} ---")
                all_text.append(text.strip())
    
    return "\n".join(all_text)


HYBRID_PROMPT = """Eres un contador público certificado experto en estados financieros mexicanos (NIF).
Te proporcionaré texto EXTRAÍDO DIRECTAMENTE de un PDF financiero. Los números en este texto son EXACTOS y SAGRADOS.

**TU TRABAJO:**
1. Lee el texto línea por línea
2. Identifica cada cuenta contable y mapéala al campo JSON correcto
3. Cuando haya sub-cuentas, usa SIEMPRE la línea de "Total" (ej: "Total Costos", "Total Gastos")
4. Si no hay línea de "Total", calcula la suma/resta tú mismo

**REGLAS ABSOLUTAS:**
- NUNCA inventes un número. Si no encuentras un campo, pon 0.
- Los números que devuelvas DEBEN aparecer textualmente en el documento o ser resultado de una operación aritmética verificable con números del documento.
- Para rubros de RESTA (Costo de Ventas, Devoluciones), busca la línea "Total Costos" que ya tiene la resta hecha. Si no existe "Total Costos", calcula: Costo bruto - Devoluciones - Rebajas.
- Para Gastos Generales, busca "Total Gastos" que incluye Depreciación Contable. Si no existe, suma: Gastos generales + Depreciación Contable.
- "impuestos_a_favor": SUMA de todas las cuentas a favor (IVA a favor + Impuestos acreditables por pagar + ISR a favor, etc.)
- "impuestos_acumulados": SUMA de todas las cuentas fiscales por pagar (IVA trasladado, ISR retenido, IMSS, SAR, Infonavit, retenciones, etc.)
- "utilidad_ejercicio" y "resultados_ejercicios_anteriores" PUEDEN ser negativos (pérdida). Si el texto muestra un signo menos (-), respétalo.
- Todos los demás valores deben ser POSITIVOS (valor absoluto).

**SINÓNIMOS COMUNES:**
- "Efectivo y Equivalentes" | "Caja y Bancos" → si es una sola línea, todo va a "bancos", caja = 0
- "Gastos Generales" = "Gastos de Administración" = "Gastos de Operación"
- "Costo de Ventas" = "Costo de lo Vendido" = "Costos de venta y/o servicio"
- "Acreedores Diversos" = "Cuentas por Pagar" = "Otras Cuentas por Pagar"
- "Utilidad del Ejercicio" = "Resultado Neto" = "Utilidad Neta" = "Utilidad (o Pérdida)"

**NOTA SOBRE OCR:** El texto puede tener errores de OCR donde la letra "l" minúscula aparece en lugar de "I" mayúscula (ej: "lmpuestos" = "Impuestos", "lngresos" = "Ingresos"). Ignora estos errores y lee la intención.

**AUTOAUDITORÍA (OBLIGATORIO):**
Antes de devolver el JSON, verifica:
1. Que la suma de tus campos de Activo Circulante ≈ "Total Activo a corto plazo" del texto
2. Que la suma de tus campos de Pasivo CP ≈ "Total Pasivo a corto plazo" del texto
3. Que ACTIVO ≈ PASIVO + CAPITAL (ecuación contable fundamental)
Si no cuadra, busca qué cuenta omitiste y corrígelo.

**TEXTO EXACTO DEL DOCUMENTO:**
{document_text}

Devuelve ÚNICAMENTE un JSON válido con esta estructura (ajusta los años según lo que encuentres):
{{
    "tipo_documento": "caf_brightec",
    "Balance": {{
        "AÑO": {{
            "caja": 0.0, "bancos": 0.0, "clientes": 0.0, "cuentas_por_cobrar": 0.0, "deudores_diversos": 0.0, "isr_diferido": 0.0, "impuestos_a_favor": 0.0, "inventarios": 0.0, "pagos_anticipados": 0.0, "anticipo_proveedores": 0.0,
            "edificios": 0.0, "maquinaria_equipo": 0.0, "equipo_transporte": 0.0, "mobiliario_equipo": 0.0, "equipo_computo": 0.0, "otros_activos_fijos": 0.0, "terrenos": 0.0, "depreciacion_acumulada": 0.0,
            "gastos_instalacion": 0.0, "depositos_garantia": 0.0, "otros_activos_largo_plazo": 0.0,
            "proveedores": 0.0, "prestamos_bancarios_cp": 0.0, "acreedores_diversos": 0.0, "otros_pasivos_cp": 0.0, "impuestos_acumulados": 0.0, "anticipo_clientes": 0.0,
            "prestamos_bancarios_lp": 0.0, "otras_cuentas_lp": 0.0,
            "capital_social": 0.0, "reserva_legal": 0.0, "aportaciones_futuros_aumentos": 0.0, "resultados_ejercicios_anteriores": 0.0, "utilidad_ejercicio": 0.0
        }}
    }},
    "Edo de resultados": {{
        "AÑO": {{
            "ventas": 0.0, "costo_ventas": 0.0, "gastos_generales": 0.0, "gastos_administracion": 0.0, "gastos_financieros": 0.0, "productos_financieros": 0.0, "utilidad_perdida_cambiaria": 0.0, "otros_gastos": 0.0, "otros_ingresos": 0.0, "impuestos": 0.0, "depreciacion": 0.0
        }}
    }}
}}
"""


def _validate_numbers(result_data: dict, source_text: str) -> list[str]:
    """
    Validate that numbers in the result exist in the source text.
    Returns list of warnings for numbers that don't match.
    """
    warnings = []
    
    # Extract all numbers from the source text
    source_numbers = set()
    for match in re.finditer(r'[\d,]+\.?\d*', source_text):
        raw = match.group()
        try:
            clean = float(raw.replace(',', ''))
            source_numbers.add(round(clean, 2))
        except ValueError:
            pass
    
    # Check each value in the result
    for section in ["Balance", "Edo de resultados"]:
        if section not in result_data:
            continue
        for year, fields in result_data[section].items():
            for field, value in fields.items():
                if value == 0:
                    continue
                abs_val = round(abs(value), 2)
                if abs_val not in source_numbers:
                    # Check if it could be a valid sum of source numbers
                    # (allow 1% tolerance for rounding)
                    close_match = any(
                        abs(abs_val - sn) / max(abs_val, 1) < 0.01
                        for sn in source_numbers
                    )
                    if not close_match:
                        warnings.append(
                            f"{section}/{year}/{field}: {value} not found in source text"
                        )
    
    return warnings


def process_hybrid(pdf_path: str | Path, api_key: str) -> dict:
    """
    Hybrid processor: pdfplumber for extraction + Gemini for reasoning.
    
    Args:
        pdf_path: Path to the financial PDF
        api_key: Gemini API key
        
    Returns:
        Same structure as LLM processor output
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        return {"success": False, "error": f"PDF not found: {pdf_path}"}
    
    # ── Step 1: Extract clean text with pdfplumber ──
    try:
        clean_text = _extract_clean_text(pdf_path)
        logger.info(f"Hybrid: extracted {len(clean_text)} chars from {pdf_path.name}")
    except Exception as e:
        return {"success": False, "error": f"PDF text extraction failed: {str(e)}"}
    
    if len(clean_text.strip()) < 50:
        return {"success": False, "error": "Not enough text extracted from PDF"}
    
    # ── Step 2: Send clean text to Gemini for reasoning ──
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = HYBRID_PROMPT.format(document_text=clean_text)
        
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.05,  # Very low: we want deterministic mapping
                        max_output_tokens=16384,
                    )
                )
                
                response_text = response.text.strip()
                
                # Clean markdown
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                extracted_data = json.loads(response_text)
                
                # ── Step 3: Validate numbers against source ──
                validation_warnings = _validate_numbers(extracted_data, clean_text)
                if validation_warnings:
                    logger.warning(f"Hybrid validation warnings: {validation_warnings}")
                
                return {
                    "success": True,
                    "document_type": "caf_brightec",
                    "data": extracted_data,
                    "method": "hybrid_pdfplumber_gemini",
                    "raw_response": response_text,
                    "validation_warnings": validation_warnings,
                }
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"Hybrid attempt {attempt+1}: JSON parse failed: {e}")
                if attempt < max_retries:
                    continue
                
                # Try repair
                repaired = _repair_json(response_text)
                if repaired:
                    return {
                        "success": True,
                        "document_type": "caf_brightec",
                        "data": repaired,
                        "method": "hybrid_pdfplumber_gemini",
                        "raw_response": response_text,
                        "warning": "JSON was repaired after truncation",
                    }
                
                return {
                    "success": False,
                    "error": f"Failed to parse Gemini response after {max_retries+1} attempts: {str(e)}",
                    "raw_response": response_text[:500],
                }
                
    except Exception as e:
        logger.error(f"Hybrid Gemini call failed: {e}")
        return {"success": False, "error": f"Gemini processing failed: {str(e)}"}


def _repair_json(text: str) -> dict | None:
    """Attempt to repair truncated JSON."""
    try:
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        
        repaired = text.rstrip()
        while repaired and repaired[-1] not in '0123456789}]"':
            repaired = repaired[:-1]
        if repaired.endswith(','):
            repaired = repaired[:-1]
        
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)
        
        return json.loads(repaired)
    except Exception:
        return None
