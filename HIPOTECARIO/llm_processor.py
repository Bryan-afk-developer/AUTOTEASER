import json
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

BURO_CREDITO_PROMPT = """Eres un experto analista de riesgo crediticio. Analiza el siguiente texto extraído de un Reporte de Buró de Crédito (MOPs) y extrae TODOS los datos relevantes.
REGLA ESTRICTA: Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni texto extra.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
Extrae la información histórica de pagos (MOPs), cuentas activas, saldos y atrasos.
El JSON debe tener la siguiente estructura exacta:

{{
    "tipo_documento": "buro_credito",
    "titular": "nombre de la persona o empresa",
    "rfc": "RFC si está disponible",
    "fecha_consulta": "YYYY-MM-DD",
    "resumen_creditos": {{
        "total_cuentas": 0,
        "cuentas_abiertas": 0,
        "cuentas_cerradas": 0,
        "saldo_actual_total": 0.0,
        "saldo_vencido_total": 0.0
    }},
    "historico_pagos_mops": [
        {{
            "institucion": "nombre del banco o financiera",
            "numero_cuenta": "número parcial o completo",
            "tipo_credito": "automotriz, tarjeta, hipotecario, etc.",
            "saldo_actual": 0.0,
            "saldo_vencido": 0.0,
            "peor_atraso_mop": "ejemplo: 02, 03, 04, UR, etc.",
            "historia_detallada": "cadena con el histórico (ej: 11112211)"
        }}
    ],
    "alertas_riesgo": [
        "lista de strings con hallazgos de riesgo (ej: 'Cuenta en cobranza', 'Atraso mayor a 90 días')"
    ]
}}
"""

ESTADO_CUENTA_PROMPT = """Eres un experto analista financiero. Analiza el siguiente texto extraído de un estado de cuenta bancario y extrae TODOS los datos financieros relevantes.
REGLA ESTRICTA: Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni texto extra.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
Extrae la siguiente información:

{{
    "tipo_documento": "estado_de_cuenta",
    "institucion": "nombre del banco",
    "titular": "nombre del titular",
    "rfc": "RFC si está disponible",
    "periodo": "periodo que cubre",
    "fecha_corte": "YYYY-MM-DD",
    "numero_cuenta": "número de cuenta principal",
    "clabe": "CLABE interbancaria si está disponible",
    "moneda": "MXN | USD | otro",
    "resumen": {{
        "saldo_inicial": 0.0,
        "total_depositos": 0.0,
        "total_retiros": 0.0,
        "saldo_final": 0.0
    }},
    "movimientos": [
        {{
            "fecha": "YYYY-MM-DD",
            "concepto": "descripción",
            "cargo": 0.0,
            "abono": 0.0,
            "saldo": 0.0
        }}
    ]
}}
"""

COMPROBANTE_DOMICILIO_PROMPT = """Eres un experto en validación de identidad y KYC. Analiza el siguiente texto extraído de un comprobante de domicilio (luz, agua, teléfono, etc.).
REGLA ESTRICTA: Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni texto extra.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
Extrae la información para validar la dirección. Estructura requerida:

{{
    "tipo_documento": "comprobante_domicilio",
    "proveedor": "CFE | Telmex | Agua | Izzi | otro",
    "titular": "nombre completo a quien está el recibo",
    "direccion": {{
        "calle_y_numero": "",
        "colonia": "",
        "codigo_postal": "",
        "municipio_o_alcaldia": "",
        "estado": "",
        "direccion_completa_cruda": "texto completo de la dirección como aparece"
    }},
    "periodo_facturacion": "periodo que cubre",
    "fecha_emision": "YYYY-MM-DD o aproximado",
    "total_a_pagar": 0.0
}}
"""

INE_PROMPT = """Eres un experto en validación de identidad KYC. Analiza el siguiente texto extraído de una Credencial para Votar (INE/IFE).
REGLA ESTRICTA: Devuelve ÚNICAMENTE un objeto JSON válido, sin markdown ni texto extra.

TEXTO DEL DOCUMENTO:
{document_text}

INSTRUCCIONES:
Extrae la siguiente información estructurada:

{{
    "tipo_documento": "identificacion_oficial",
    "subtipo": "INE | IFE",
    "nombre_completo": {{
        "nombres": "",
        "apellido_paterno": "",
        "apellido_materno": ""
    }},
    "curp": "",
    "clave_elector": "",
    "seccion": "",
    "fecha_nacimiento": "YYYY-MM-DD o DD/MM/YYYY",
    "sexo": "H | M",
    "direccion": "Dirección completa impresa",
    "año_registro": "",
    "vigencia": "Año de vencimiento (ej: 2030)"
}}
"""

def detect_document_type(text: str) -> str:
    text_lower = text.lower()
    
    # Simple keyword scoring
    scores = {
        "buro_credito": sum(1 for kw in ["buró de crédito", "histórico de pagos", "mop", "comportamiento crediticio", "claves de prevención"] if kw in text_lower),
        "estado_de_cuenta": sum(1 for kw in ["estado de cuenta", "saldo inicial", "saldo final", "clabe", "depósitos", "retiros"] if kw in text_lower),
        "comprobante_domicilio": sum(1 for kw in ["total a pagar", "cfe", "telmex", "recibo", "domicilio", "consumo"] if kw in text_lower),
        "ine": sum(1 for kw in ["credencial para votar", "instituto nacional electoral", "clave de elector", "curp", "año de registro"] if kw in text_lower)
    }
    
    best = max(scores, key=scores.get)
    if scores[best] >= 1:
        return best
    return "desconocido"

def get_prompt_for_type(doc_type: str) -> str:
    prompts = {
        "buro_credito": BURO_CREDITO_PROMPT,
        "estado_de_cuenta": ESTADO_CUENTA_PROMPT,
        "comprobante_domicilio": COMPROBANTE_DOMICILIO_PROMPT,
        "ine": INE_PROMPT
    }
    return prompts.get(doc_type, ESTADO_CUENTA_PROMPT) # fallback

def analyze_document(text: str, doc_type: str = None) -> dict:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no configurada en config.py / .env")
        
    genai.configure(api_key=GEMINI_API_KEY)
    
    if not doc_type or doc_type == "desconocido":
        doc_type = detect_document_type(text)
        
    prompt = get_prompt_for_type(doc_type).format(document_text=text)
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
            )
        )
        
        # Parse and clean JSON
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        return json.loads(response_text.strip())
        
    except Exception as e:
        logger.error(f"Error procesando con Gemini: {e}")
        return {"error": str(e), "raw_text": text}
