import json
import logging
from app.llm_processor import configure_gemini
from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(__name__)

def map_financial_data(extracted_text: str, concepts_dict: dict) -> dict:
    """
    Map raw financial text into structured JSON matching the requested concepts.
    
    concepts_dict format:
    {
      "Balance": ["caja", "bancos", ...],
      "Edo de resultados": ["ventas", "costo_ventas", ...]
    }
    """
    configure_gemini()
    
    model = GenerativeModel("gemini-2.5-flash")
    
    prompt = f"""Eres un experto contador y analista financiero.
He extraído el texto de un estado financiero (Balance General y Estado de Resultados).
Quiero que extraigas los valores numéricos correspondientes a los siguientes conceptos financieros.

CONCEPTOS SOLICITADOS:
{json.dumps(concepts_dict, indent=2, ensure_ascii=False)}

TEXTO DEL ESTADO FINANCIERO:
{extracted_text}

INSTRUCCIONES:
1. Devuelve un objeto JSON con la estructura principal "Balance" y "Edo de resultados" (como se solicitó).
2. Agrega una clave principal llamada "anio" cuyo valor sea el año al que corresponde este estado financiero (ej. "2023", "2024"). Si no estás seguro, pon "Desconocido".
3. Las subclaves de Balance y Edo de resultados son los conceptos, y los valores deben ser números flotantes (float).
4. Si un concepto no se encuentra, o está explícitamente en ceros o rayas, asigna el valor 0.0.
5. Elimina comas y símbolos de moneda.
6. No incluyas información adicional, sólo el JSON estructurado.
"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        text = response.text
        # Sometimes Gemini wraps json in ```json ... ``` even with response_mime_type
        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()
        
        return json.loads(text)
    except Exception as e:
        logger.error(f"Error calling Gemini in map_financial_data: {e}")
        return {}
