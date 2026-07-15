import json
import logging
import fitz

logger = logging.getLogger(__name__)

PROMPT_ACTA = """
Eres un analista legal experto en México.
Analiza el siguiente texto de un acta constitutiva, asamblea o poder notarial y extrae la información en formato JSON estrictamente. Si algún campo no aplica o no se encuentra, usa null.

{
  "razon_social": "Nombre completo de la empresa / sociedad",
  "tipo_documento": "Ej: Acta Constitutiva, Asamblea Extraordinaria, Poder Notarial, etc.",
  "numero_acta": "Número de acta, escritura o póliza. IMPORTANTÍSIMO: Busca primero en la portada o primera página (ej. 'ACTA 360-2023'). Si hay varios números a lo largo del documento (ej. 'Acta número CIEN'), prioriza SIEMPRE el número que aparece en la primera página/portada. Si de plano no hay ninguno en la portada, busca en el resto del texto.",
  "fecha_documento": "Fecha en la que se realizó el acta en formato YYYY-MM-DD si la encuentras, si no null",
  "accionistas": [
    {
      "nombre": "Nombre completo del accionista",
      "participacion": "Porcentaje (ej: 50%) o número de acciones (ej: 100 acciones) o capital aportado, si se menciona. De lo contrario null"
    }
  ],
  "administrador_unico": "Nombre completo de la persona o personas que quedan designadas como Administrador Único, Administrador General o Presidente del Consejo de Administración. Si no se menciona explícitamente, usa null.",
  "poderes": "Resumen de quién tiene poderes legales (representantes) y qué tipo de poderes tienen",
  "resumen": "Resumen ejecutivo de máximo 3 líneas del contenido principal."
}

Responde ÚNICAMENTE con el JSON, sin texto adicional, sin bloques de código markdown.

TEXTO DEL ACTA:
"""

def _ocr_with_docai(pdf_bytes: bytes, max_pages: int = 30) -> str:
    """Extrae texto de un PDF escaneado usando Google Cloud Document AI Basic OCR."""
    from google.cloud import documentai
    from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_BASIC_OCR, GCP_PROCESSOR_ID_OCR
    
    processor_id = GCP_PROCESSOR_ID_BASIC_OCR or GCP_PROCESSOR_ID_OCR
    if not GCP_PROJECT_ID or not processor_id:
        raise ValueError("GCP_PROJECT_ID o GCP_PROCESSOR_ID no configurados en .env")
    
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, processor_id)
    
    # Document AI tiene un límite de 15 páginas por llamada y 20MB
    doc_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    n_pages = min(len(doc_pdf), max_pages)
    BATCH_SIZE = 15
    
    full_text = ""
    for i in range(0, n_pages, BATCH_SIZE):
        batch_doc = fitz.open()
        end = min(i + BATCH_SIZE, n_pages)
        batch_doc.insert_pdf(doc_pdf, from_page=i, to_page=end - 1)
        batch_bytes = batch_doc.tobytes()
        batch_doc.close()
        
        raw_document = documentai.RawDocument(content=batch_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        full_text += result.document.text + "\n"
        logger.info(f"DocAI OCR: páginas {i+1}-{end} de {n_pages} procesadas")
    
    doc_pdf.close()
    return full_text.strip()


def _analyze_with_gemini_api_key(text: str) -> dict:
    """
    Llama a Gemini via Vertex AI.
    """
    from app.llm_processor import configure_gemini
    from vertexai.generative_models import GenerativeModel
    
    configure_gemini()
    prompt = PROMPT_ACTA + text[:30000]
    
    model = GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,
            "max_output_tokens": 8192,
        }
    )
    
    ai_text = response.text.strip()

    if ai_text.startswith("```json"):
        ai_text = ai_text[7:].strip()
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3].strip()
    elif ai_text.startswith("```"):
        ai_text = ai_text[3:].strip()
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3].strip()

    try:
        return json.loads(ai_text)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing Gemini response: {e}")
        return {}


def analyze_acta(pdf_bytes: bytes) -> dict:
    # Intentar extracción de texto nativo primero (PDFs digitales — gratis)
    text_content = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc[:30]:
            text_content += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        logger.warning(f"No se pudo extraer texto nativo: {e}")

    # Si el PDF es escaneado (sin texto), usar Document AI OCR
    if not text_content.strip() or len(text_content.strip()) < 100:
        logger.info("PDF sin texto nativo -> usando Document AI Basic OCR")
        try:
            text_content = _ocr_with_docai(pdf_bytes)
        except Exception as e:
            logger.error(f"Error Document AI OCR: {e}")
            raise RuntimeError(f"Error al procesar el PDF con OCR: {e}")

    if not text_content.strip():
        raise RuntimeError("No se pudo extraer texto del documento, incluso con OCR.")

    # Analizar con Gemini
    try:
        ai_data = _analyze_with_gemini_api_key(text_content)
    except Exception as e:
        logger.error(f"Error Gemini: {e}")
        raise RuntimeError(f"Error al analizar el texto con IA: {e}")

    return ai_data
