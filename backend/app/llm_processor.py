"""
LLM Processor module.
Uses Google Gemini to analyze financial document text and extract structured data.
"""
import json
import logging
import vertexai
from vertexai.generative_models import GenerativeModel
from app.config import GEMINI_API_KEY, GCP_PROJECT_ID, VERTEX_LOCATION

logger = logging.getLogger(__name__)


# Financial data extraction prompt templates
ESTADO_CUENTA_PROMPT = """Eres un experto analista financiero. Analiza el siguiente texto extraído de un estado de cuenta bancario y extrae TODOS los datos financieros relevantes.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
1. Identifica el tipo de documento (estado de cuenta, balance general, estado de resultados, etc.)
2. Extrae todos los campos financieros que encuentres
3. Responde ÚNICAMENTE en formato JSON válido

Extrae la siguiente información si está disponible:

{{
    "tipo_documento": "estado_de_cuenta | balance_general | estado_resultados | otro",
    "institucion": "nombre del banco o institución",
    "titular": "nombre del titular de la cuenta",
    "periodo": "periodo que cubre el documento",
    "fecha_corte": "fecha de corte o emisión",
    "numero_cuenta": "número de cuenta",
    "moneda": "MXN | USD | otro",
    
    "saldo_inicial": 0.0,
    "saldo_final": 0.0,
    "total_depositos": 0.0,
    "total_retiros": 0.0,
    "total_comisiones": 0.0,
    "intereses_generados": 0.0,
    "iva_cobrado": 0.0,
    
    "movimientos": [
        {{
            "fecha": "YYYY-MM-DD",
            "concepto": "descripción del movimiento",
            "referencia": "referencia o folio",
            "cargo": 0.0,
            "abono": 0.0,
            "saldo": 0.0
        }}
    ],
    
    "resumen_mensual": {{
        "total_ingresos": 0.0,
        "total_egresos": 0.0,
        "saldo_promedio": 0.0,
        "numero_transacciones": 0
    }},
    
    "datos_adicionales": {{}}
}}

IMPORTANTE:
- Todos los montos deben ser numéricos (sin símbolos de moneda ni comas)
- Las fechas deben estar en formato YYYY-MM-DD cuando sea posible
- Si un campo no está disponible, usa null
- Si el documento tiene múltiples páginas, consolida la información
- Captura TODOS los movimientos que puedas identificar
- Responde SOLO con el JSON, sin texto adicional
"""

BALANCE_GENERAL_PROMPT = """Eres un experto contador público. Analiza el siguiente texto extraído de un Balance General y extrae TODOS los datos financieros.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
Extrae la siguiente información en formato JSON:

{{
    "tipo_documento": "balance_general",
    "empresa": "nombre de la empresa",
    "periodo": "periodo o fecha del balance",
    "fecha": "fecha del balance",
    "moneda": "MXN | USD",
    
    "activo": {{
        "activo_circulante": {{
            "caja_y_bancos": 0.0,
            "inversiones_temporales": 0.0,
            "clientes": 0.0,
            "cuentas_por_cobrar": 0.0,
            "documentos_por_cobrar": 0.0,
            "inventarios": 0.0,
            "pagos_anticipados": 0.0,
            "iva_acreditable": 0.0,
            "otros_activos_circulantes": 0.0,
            "total_activo_circulante": 0.0
        }},
        "activo_fijo": {{
            "terrenos": 0.0,
            "edificios": 0.0,
            "maquinaria_y_equipo": 0.0,
            "equipo_de_transporte": 0.0,
            "equipo_de_computo": 0.0,
            "mobiliario_y_equipo": 0.0,
            "depreciacion_acumulada": 0.0,
            "otros_activos_fijos": 0.0,
            "total_activo_fijo": 0.0
        }},
        "activo_diferido": {{
            "gastos_de_organizacion": 0.0,
            "gastos_de_instalacion": 0.0,
            "otros_activos_diferidos": 0.0,
            "total_activo_diferido": 0.0
        }},
        "total_activo": 0.0
    }},
    
    "pasivo": {{
        "pasivo_circulante": {{
            "proveedores": 0.0,
            "cuentas_por_pagar": 0.0,
            "documentos_por_pagar": 0.0,
            "impuestos_por_pagar": 0.0,
            "iva_por_pagar": 0.0,
            "acreedores_diversos": 0.0,
            "otros_pasivos_circulantes": 0.0,
            "total_pasivo_circulante": 0.0
        }},
        "pasivo_largo_plazo": {{
            "prestamos_bancarios": 0.0,
            "hipotecas_por_pagar": 0.0,
            "otros_pasivos_largo_plazo": 0.0,
            "total_pasivo_largo_plazo": 0.0
        }},
        "total_pasivo": 0.0
    }},
    
    "capital_contable": {{
        "capital_social": 0.0,
        "reserva_legal": 0.0,
        "resultado_ejercicios_anteriores": 0.0,
        "resultado_del_ejercicio": 0.0,
        "otras_cuentas_capital": 0.0,
        "total_capital_contable": 0.0
    }},
    
    "total_pasivo_mas_capital": 0.0,
    
    "datos_adicionales": {{}}
}}

IMPORTANTE:
- Todos los montos deben ser numéricos
- Si un campo no está disponible, usa null
- Responde SOLO con el JSON, sin texto adicional
"""

GENERIC_FINANCIAL_PROMPT = """Eres un experto analista financiero. Analiza el siguiente texto extraído de un documento financiero y extrae toda la información relevante.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
1. Primero identifica el tipo de documento financiero
2. Extrae todos los datos numéricos y campos relevantes
3. Organiza la información de manera estructurada

Responde en formato JSON con la siguiente estructura base:

{{
    "tipo_documento": "tipo identificado",
    "empresa_o_titular": "nombre",
    "periodo": "periodo del documento",
    "fecha": "fecha del documento",
    "moneda": "moneda utilizada",
    "datos_principales": {{
        "descripción de cada campo encontrado": "valor"
    }},
    "totales": {{
        "descripción de totales": 0.0
    }},
    "detalle_movimientos": [
        {{
            "fecha": "fecha",
            "concepto": "descripción",
            "monto": 0.0,
            "tipo": "ingreso | egreso"
        }}
    ],
    "observaciones": "cualquier observación relevante"
}}

IMPORTANTE:
- Todos los montos deben ser numéricos
- Responde SOLO con el JSON válido
"""


CAF_BRIGHTEC_PROMPT = """Eres un analista financiero experto y contador público certificado. Extrae los datos del Balance General y Estado de Resultados del documento financiero adjunto.
**REGLA ESTRICTA:** Devuelve ÚNICAMENTE un objeto JSON válido con la estructura exacta que se muestra abajo. No incluyas texto adicional, ni saludos, ni bloques de código markdown.
Si un rubro no existe en el documento para un año específico, asigna el valor 0. No uses comas para los miles, solo números puros o decimales.
**IMPORTANTE:** Extrae todos los años disponibles en el documento (pueden ser desde 1 hasta 4 años). Usa el año real de 4 dígitos como llave (ejemplo: "2024", "2025").

REGLAS CONTABLES ESTRICTAS PARA EXTRAER Y CALCULAR:
Las empresas usan distintos formatos. NO extraigas solo el primer número que coincida con el nombre. DEBES calcular los totales aplicando estas reglas:

1. **Costo de Ventas**: Si el documento muestra "Costo de Ventas" y justo debajo "Devoluciones", "Rebajas" o "Descuentos", DEBES restar esas devoluciones al costo de ventas base y devolver el resultado NETO (es decir, usa "Total Costos" si existe). Ejemplo: Costo de venta $1,660,338 - Devoluciones $73,831 = costo_ventas: 1586507.76

2. **Gastos Generales / Gastos de Operación**: Busca el TOTAL del grupo. Si la "Depreciación Contable" está desglosada como parte de los Gastos Generales (o gastos de administración), el valor de "gastos_generales" debe ser el Total Gastos que ya incluye la depreciación. NO sumes por tu cuenta si el total ya la incluye. Usa la fila de "Total Gastos" si existe.

3. **Depreciación (Edo de Resultados)**: Extrae la Depreciación Contable que aparezca dentro del Estado de Resultados como un rubro separado. Este valor va en "depreciacion".

4. **Caja y Bancos (Cuentas Agrupadas)**: Si el documento une conceptos, por ejemplo "Efectivo y Equivalentes" o "Caja y Bancos" en una sola fila, asigna el 100% de ese valor a la llave "bancos" y pon "caja": 0. No intentes adivinar cómo se divide.

5. **Búsqueda de Sinónimos**: Los nombres varían entre empresas:
   - "Gastos Generales" = "Gastos de Administración" = "Gastos de Operación"
   - "Cuentas por Cobrar" = "Deudores" = "Clientes y Cuentas por Cobrar"
   - "Acreedores Diversos" = "Cuentas por Pagar" = "Otras Cuentas por Pagar"
   - "Utilidad del Ejercicio" = "Resultado Neto" = "Utilidad Neta"
   Relaciona el concepto contable correcto según las NIF (Normas de Información Financiera).

6. **Todos los valores deben ser POSITIVOS** (valores absolutos). El sistema se encarga de aplicar los signos negativos automáticamente. Si el PDF muestra un número negativo como -$50,000 o ($50,000), extrae el valor absoluto: 50000.

7. **Signos negativos del PDF**: PRESTA ATENCIÓN ESPECIAL a signos negativos. Si un valor aparece con signo menos (-), entre paréntesis, o el texto dice "menos" o "negativo", eso indica que el valor real es negativo. Para rubros como "utilidad_ejercicio", "resultados_ejercicios_anteriores" o "utilidad_perdida_cambiaria", SI el PDF los muestra negativos (pérdida), devuélvelos negativos. Para los demás rubros, devuélvelos siempre positivos.

8. **Cuentas que se deben SUMAR (Agrupación de subcuentas)**: Muchas empresas desglosan un concepto en varias líneas. DEBES sumar TODAS las sub-líneas:
   - "impuestos_a_favor": Suma TODO lo que sea a favor del contribuyente: IVA a favor, IVA acreditable, ISR a favor, Impuestos acreditables por pagar, Subsidio al empleo, etc. Si el PDF tiene "Impuesto a favor: $100" e "Impuestos acreditables por pagar: $200", entonces impuestos_a_favor = 300.
   - "impuestos_acumulados": Suma TODO lo que la empresa debe al fisco: IVA trasladado, ISR retenido, ISR por pagar, IMSS por pagar, SAR, Infonavit, Retenciones ISR, Cuotas IMSS, Provisiones fiscales.
   - "acreedores_diversos": Suma TODAS las cuentas por pagar que NO sean proveedores ni impuestos ni préstamos bancarios.
   - "otros_pasivos_cp": Si quedan cuentas de pasivo a corto plazo que no encajan en ninguna categoría anterior, súmalas aquí.

9. **REGLA DE CUADRE Y AUTOAUDITORÍA (¡OBLIGATORIO!)**:
   Antes de generar el JSON final, DEBES verificar matemáticamente tu trabajo contra los totales impresos en el PDF:
   - Suma mentalmente todos los conceptos que agrupaste para cada sección (Activo Circulante, Activo Fijo, Pasivo CP, Pasivo LP, Capital).
   - Compara tu suma con el renglón "Total" correspondiente en el PDF (ej: "Total Pasivo a corto plazo", "Total Activo Circulante").
   - SI TU SUMA ES MENOR AL TOTAL DEL PDF: Significa que OMITISTE cuentas. Vuelve a revisar renglón por renglón buscando conceptos escondidos (provisiones, IMSS, SAR, Infonavit, retenciones, etc.) e inclúyelos en el campo más apropiado hasta que tu suma CUADRE con el PDF.
   - La ecuación fundamental ACTIVO = PASIVO + CAPITAL debe cumplirse con los números que devuelvas.
   - Si no cuadra, revisa qué te faltó y corrígelo ANTES de devolver el JSON.

TEXTO DEL DOCUMENTO:
{document_text}

Estructura requerida (agrega o quita años según lo que encuentres en el documento):
{{
    "tipo_documento": "caf_brightec",
    "Balance": {{
        "2024": {{
            "caja": 0.0, "bancos": 0.0, "clientes": 0.0, "cuentas_por_cobrar": 0.0, "deudores_diversos": 0.0, "isr_diferido": 0.0, "impuestos_a_favor": 0.0, "inventarios": 0.0, "pagos_anticipados": 0.0, "anticipo_proveedores": 0.0,
            "edificios": 0.0, "maquinaria_equipo": 0.0, "equipo_transporte": 0.0, "mobiliario_equipo": 0.0, "equipo_computo": 0.0, "otros_activos_fijos": 0.0, "terrenos": 0.0, "depreciacion_acumulada": 0.0,
            "gastos_instalacion": 0.0, "depositos_garantia": 0.0, "otros_activos_largo_plazo": 0.0,
            "proveedores": 0.0, "prestamos_bancarios_cp": 0.0, "acreedores_diversos": 0.0, "otros_pasivos_cp": 0.0, "impuestos_acumulados": 0.0, "anticipo_clientes": 0.0,
            "prestamos_bancarios_lp": 0.0, "otras_cuentas_lp": 0.0,
            "capital_social": 0.0, "reserva_legal": 0.0, "aportaciones_futuros_aumentos": 0.0, "resultados_ejercicios_anteriores": 0.0, "utilidad_ejercicio": 0.0
        }},
        "2025": {{
            "caja": 0.0, "bancos": 0.0, "clientes": 0.0, "cuentas_por_cobrar": 0.0, "deudores_diversos": 0.0, "isr_diferido": 0.0, "impuestos_a_favor": 0.0, "inventarios": 0.0, "pagos_anticipados": 0.0, "anticipo_proveedores": 0.0,
            "edificios": 0.0, "maquinaria_equipo": 0.0, "equipo_transporte": 0.0, "mobiliario_equipo": 0.0, "equipo_computo": 0.0, "otros_activos_fijos": 0.0, "terrenos": 0.0, "depreciacion_acumulada": 0.0,
            "gastos_instalacion": 0.0, "depositos_garantia": 0.0, "otros_activos_largo_plazo": 0.0,
            "proveedores": 0.0, "prestamos_bancarios_cp": 0.0, "acreedores_diversos": 0.0, "otros_pasivos_cp": 0.0, "impuestos_acumulados": 0.0, "anticipo_clientes": 0.0,
            "prestamos_bancarios_lp": 0.0, "otras_cuentas_lp": 0.0,
            "capital_social": 0.0, "reserva_legal": 0.0, "aportaciones_futuros_aumentos": 0.0, "resultados_ejercicios_anteriores": 0.0, "utilidad_ejercicio": 0.0
        }}
    }},
    "Edo de resultados": {{
        "2024": {{
            "ventas": 0.0, "costo_ventas": 0.0, "gastos_generales": 0.0, "gastos_administracion": 0.0, "gastos_financieros": 0.0, "productos_financieros": 0.0, "utilidad_perdida_cambiaria": 0.0, "otros_gastos": 0.0, "otros_ingresos": 0.0, "impuestos": 0.0, "depreciacion": 0.0
        }},
        "2025": {{
            "ventas": 0.0, "costo_ventas": 0.0, "gastos_generales": 0.0, "gastos_administracion": 0.0, "gastos_financieros": 0.0, "productos_financieros": 0.0, "utilidad_perdida_cambiaria": 0.0, "otros_gastos": 0.0, "otros_ingresos": 0.0, "impuestos": 0.0, "depreciacion": 0.0
        }}
    }}
}}
"""


def configure_gemini():
    """Configure the Gemini API client via Vertex AI."""
    if not GCP_PROJECT_ID:
        raise ValueError(
            "GCP_PROJECT_ID no configurada. Agrega tu proyecto en el archivo .env"
        )
    vertexai.init(project=GCP_PROJECT_ID, location=VERTEX_LOCATION)


def detect_document_type(text: str) -> str:
    """
    Detect the type of financial document based on its content.
    """
    text_lower = text.lower()
    
    # Check if it's the specific Brightec CAF document
    if "brightec energy" in text_lower or "brightec" in text_lower:
        return "caf_brightec"
    
    keywords_estado_cuenta = [
        "estado de cuenta", "saldo inicial", "saldo final",
        "deposito", "retiro", "comisión", "cargo", "abono",
        "sucursal", "cuenta de cheques", "número de cuenta"
    ]
    
    keywords_balance = [
        "balance general", "activo circulante", "activo fijo",
        "pasivo circulante", "capital contable", "capital social",
        "total activo", "total pasivo"
    ]
    
    keywords_resultados = [
        "estado de resultados", "utilidad neta", "utilidad bruta",
        "costo de ventas", "gastos de operación", "ingresos por ventas"
    ]
    
    score_estado = sum(1 for kw in keywords_estado_cuenta if kw in text_lower)
    score_balance = sum(1 for kw in keywords_balance if kw in text_lower)
    score_resultados = sum(1 for kw in keywords_resultados if kw in text_lower)
    
    scores = {
        "estado_de_cuenta": score_estado,
        "balance_general": score_balance,
        "estado_de_resultados": score_resultados
    }
    
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return "generico"


def get_prompt_for_type(doc_type: str) -> str:
    """Get the appropriate prompt template for the document type."""
    prompts = {
        "caf_brightec": CAF_BRIGHTEC_PROMPT,
        "estado_de_cuenta": ESTADO_CUENTA_PROMPT,
        "balance_general": BALANCE_GENERAL_PROMPT,
        "estado_de_resultados": GENERIC_FINANCIAL_PROMPT,
        "generico": GENERIC_FINANCIAL_PROMPT
    }
    return prompts.get(doc_type, GENERIC_FINANCIAL_PROMPT)


def analyze_document(text: str, doc_type: str | None = None) -> dict:
    """
    Analyze a financial document using Google Gemini LLM.
    
    Args:
        text: The extracted text from the PDF
        doc_type: Optional document type override
        
    Returns:
        Dictionary with extracted financial data
    """
    configure_gemini()
    
    # Auto-detect document type if not provided
    if not doc_type:
        doc_type = detect_document_type(text)
    
    logger.info(f"Document type detected: {doc_type}")
    
    # Get appropriate prompt
    prompt_template = get_prompt_for_type(doc_type)
    prompt = prompt_template.format(document_text=text)
    
    # Call Gemini via Vertex AI
    model = GenerativeModel("gemini-2.5-flash")
    
    max_retries = 2
    last_error = None
    raw_text = ""
    
    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for accuracy
                    "max_output_tokens": 8192,
                }
            )
            
            # Parse JSON response
            response_text = response.text.strip()
            raw_text = response_text
            
            # Clean up response - remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            extracted_data = json.loads(response_text)
            
            return {
                "success": True,
                "document_type": doc_type,
                "data": extracted_data,
                "raw_response": response_text
            }
            
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(f"Attempt {attempt+1}/{max_retries+1}: JSON parse failed: {e}")
            
            # Try to repair truncated JSON before retrying
            if attempt < max_retries:
                logger.info(f"Retrying Gemini call (attempt {attempt+2})...")
                continue
            else:
                # Last attempt: try to repair the truncated JSON
                logger.info("All retries exhausted, attempting JSON repair...")
                repaired = _repair_truncated_json(response_text)
                if repaired:
                    return {
                        "success": True,
                        "document_type": doc_type,
                        "data": repaired,
                        "raw_response": response_text,
                        "warning": "JSON was truncated and repaired automatically"
                    }
                    
                return {
                    "success": False,
                    "document_type": doc_type,
                    "error": f"Error parsing LLM response after {max_retries+1} attempts: {str(e)}",
                    "raw_response": raw_text
                }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying Gemini call (attempt {attempt+2})...")
                continue
            return {
                "success": False,
                "document_type": doc_type,
                "error": str(e)
            }


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair a truncated JSON string by closing open braces/brackets."""
    try:
        # Count open vs close braces and brackets
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        
        # Remove any trailing comma or incomplete key/value
        repaired = text.rstrip()
        # Strip trailing partial content after last complete value
        while repaired and repaired[-1] not in '0123456789}]"':
            repaired = repaired[:-1]
        
        # If it ends with a comma, remove it
        if repaired.endswith(','):
            repaired = repaired[:-1]
            
        # Close open brackets then braces
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)
        
        result = json.loads(repaired)
        logger.info("JSON repair successful!")
        return result
    except Exception as e:
        logger.error(f"JSON repair failed: {e}")
        return None


def analyze_with_custom_template(text: str, template_fields: list[str]) -> dict:
    """
    Analyze document with specific fields from an Excel template.
    
    Args:
        text: Document text
        template_fields: List of field names from the Excel template to fill
        
    Returns:
        Dictionary mapping field names to extracted values
    """
    configure_gemini()
    
    fields_str = "\n".join([f'    "{field}": "valor extraído o null"' for field in template_fields])
    
    prompt = f"""Eres un experto analista financiero. Del siguiente documento financiero, extrae los valores para cada uno de los campos solicitados.

TEXTO DEL DOCUMENTO:
{text}

CAMPOS A EXTRAER:
{{
{fields_str}
}}

INSTRUCCIONES:
- Extrae el valor exacto para cada campo
- Los montos deben ser numéricos (sin símbolos de moneda ni comas)
- Las fechas en formato YYYY-MM-DD
- Si no encuentras un campo, usa null
- Responde SOLO con el JSON válido
"""
    
    model = GenerativeModel("gemini-2.5-flash")
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 8192,
            }
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        data = json.loads(response_text)
        
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Custom template analysis failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def analyze_excel_template(template_info: dict) -> dict:
    """
    Use Gemini to analyze the structure of an uploaded Excel template
    and return a configuration mapping to help fill it.
    """
    configure_gemini()
    
    prompt = f"""Eres un experto en automatización de Excel. Analiza la siguiente estructura extraída de una plantilla de Excel.
Tu objetivo es "configurar la salida del excel" indicando qué columnas o datos se esperan.

ESTRUCTURA DE LA PLANTILLA:
{json.dumps(template_info, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Identifica qué tipo de documento financiero es esta plantilla (ej. estado de cuenta, balance general).
2. Enumera los campos individuales requeridos (ej. saldo_inicial, titular).
3. Si hay tablas, identifica las columnas esperadas en los movimientos.
4. Responde ÚNICAMENTE con un JSON válido con esta estructura:
{{
    "tipo_plantilla_detectado": "...",
    "campos_requeridos": ["campo1", "campo2"],
    "columnas_tabla_movimientos": ["columna1", "columna2"],
    "instrucciones_mapeo": "Breve explicación de cómo se deben mapear los datos."
}}
"""
    
    model = GenerativeModel("gemini-2.5-flash")
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
            }
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Template analysis with Gemini failed: {e}")
        return {"error": str(e)}

