"""
AutoTeaser - PDF Text Extractor
Uses PyMuPDF (fitz) for high-fidelity text extraction, falling back to pdfplumber.
"""
import fitz
import pdfplumber
from pathlib import Path
import logging
import os

from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR

logger = logging.getLogger(__name__)

def extract_with_documentai(pdf_source: Path | bytes) -> list[str]:
    """
    Extracts text using Google Cloud Document AI Form Parser.
    Returns a list of strings, where each string is a JSON dictionary
    of the Key-Value pairs extracted from that page.
    """
    if not GCP_PROJECT_ID or not GCP_PROCESSOR_ID_OCR:
        logger.warning("Document AI Form Parser fallback requested, but GCP_PROJECT_ID or GCP_PROCESSOR_ID_OCR are not configured.")
        return []

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import documentai
        import json
        
        # You must set the api_endpoint if you use a location other than 'us'.
        opts = ClientOptions(api_endpoint=f"{GCP_LOCATION}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        
        name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_OCR)
        
        if isinstance(pdf_source, bytes):
            image_content = pdf_source
        else:
            with open(pdf_source, "rb") as image:
                image_content = image.read()
            
        raw_document = documentai.RawDocument(content=image_content, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        
        result = client.process_document(request=request)
        document = result.document
        
        def get_text(doc_element: dict, document_text: str) -> str:
            """Extracts text from a Document AI text anchor."""
            response = ""
            for segment in doc_element.text_anchor.text_segments:
                start_index = int(segment.start_index)
                end_index = int(segment.end_index)
                response += document_text[start_index:end_index]
            return response.strip().replace('\n', ' ')

        pages_text = []
        for page in document.pages:
            form_data = {}
            if getattr(page, "form_fields", None):
                for field in page.form_fields:
                    key = get_text(field.field_name, document.text)
                    val = get_text(field.field_value, document.text)
                    if key:
                        form_data[key] = val
            
            # Si no hay form_fields pero hay texto, metemos el texto como fallback (por si acaso)
            # o simplemente devolvemos el JSON string.
            if form_data:
                pages_text.append(json.dumps(form_data, indent=2, ensure_ascii=False))
            else:
                # Si el Form Parser no encuentra llaves-valor, intenta devolver el texto de la pagina
                page_text = ""
                if getattr(page.layout, "text_anchor", None):
                    page_text = get_text(page.layout, document.text)
                pages_text.append(page_text)
            
        # Siempre incluir el texto OCR completo del documento como último elemento.
        # Esto captura datos de tablas que el Form Parser no extrajo como llave-valor.
        if document.text:
            pages_text.append(f"--- FULL DOCUMENT TEXT ---\n{document.text}")
            
        return pages_text
    except Exception as e:
        logger.error(f"Document AI Form Parser extraction failed: {e}")
        return []


def extract_text(pdf_path: str | Path) -> dict:
    """
    Extract all text from a PDF file using PyMuPDF (fitz), with pdfplumber fallback.
    
    Returns:
        dict with keys: full_text, pages (list of page texts), page_count
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    pages_text = []
    
    try:
        # Try PyMuPDF first (much more robust at reading native PDFs with encoding issues)
        doc = fitz.open(str(pdf_path))
        for page in doc:
            text = page.get_text("text") or ""
            pages_text.append(text)
        doc.close()
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed, falling back to pdfplumber: {e}")
        pages_text = []

    # If PyMuPDF failed or returned no text, fallback to pdfplumber
    if not pages_text or sum(len(p.strip()) for p in pages_text) < 50:
        pages_text = []
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages_text.append(text)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")
            
    # Final fallback for Teaser (Estados de Cuenta): Document AI OCR
    if not pages_text or sum(len(p.strip()) for p in pages_text) < 50:
        logger.info("PDF appears scanned or protected. Attempting Google Cloud Document AI OCR fallback...")
        doc_ai_pages = extract_with_documentai(pdf_path)
        if doc_ai_pages and sum(len(p.strip()) for p in doc_ai_pages) >= 50:
            pages_text = doc_ai_pages

    full_text = "\n\n".join(pages_text)
    
    return {
        "full_text": full_text,
        "pages": pages_text,
        "page_count": len(pages_text),
    }

def extraer_nombre_csf(pdf_source: Path | bytes) -> str | None:
    """Extrae el nombre del representante desde una Constancia de Situación Fiscal (Persona Física)."""
    try:
        if isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            doc = fitz.open(pdf_source)
            
        full_text = ""
        for page in doc:
            full_text += page.get_text()
            
        import re
        
        def find_field(field_name: str) -> str:
            # Intentar buscar en la misma línea: "Campo: Valor"
            match = re.search(rf"{field_name}:?\s+([^\n]+)", full_text, re.IGNORECASE)
            if match and match.group(1).strip() and match.group(1).strip().upper() != "PRIMER APELLIDO":
                # Ensure we don't accidentally capture the next label if it's empty
                return match.group(1).strip()
            
            # Si no, buscar en la línea siguiente (PyMuPDF a veces separa la llave y el valor por salto de línea)
            match = re.search(rf"{field_name}:?\s*\n+([^\n]+)", full_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return ""

        n = find_field(r"Nombre\s*\(s\)")
        a1 = find_field(r"Primer Apellido")
        a2 = find_field(r"Segundo Apellido")
        
        if n or a1 or a2:
            return f"{n} {a1} {a2}".strip().replace("  ", " ")
            
    except Exception as e:
        logger.error(f"Error extraeyendo nombre de CSF: {e}")
        
    return None

def extraer_nombre_ine(pdf_source: Path | bytes) -> str | None:
    """Extrae el nombre del representante desde un INE usando Document AI."""
    try:
        pages_text = extract_with_documentai(pdf_source)
        full_text = "\n".join(pages_text)
        
        import json, re
        
        # 1. Intentar buscar en los campos JSON extraídos por el Form Parser
        for pt in pages_text:
            if pt.strip().startswith("{"):
                try:
                    data = json.loads(pt)
                    for k, v in data.items():
                        if "NOMBRE" in k.upper():
                            val = str(v).strip().replace("\n", " ")
                            if val and len(val) > 2:
                                return val
                except:
                    pass
                    
        # 2. Si no, buscar en el texto OCR crudo (Fallback manual)
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            if line.upper() == "NOMBRE":
                # En un INE, el orden suele ser:
                # NOMBRE
                # APELLIDO PATERNO
                # APELLIDO MATERNO
                # NOMBRE(S)
                if i + 3 < len(lines):
                    ap1 = lines[i+1]
                    ap2 = lines[i+2]
                    nom = lines[i+3]
                    # Solo retornar si no parecen etiquetas
                    if "DOMICILIO" not in ap1.upper() and "FOLIO" not in nom.upper():
                        return f"{nom} {ap1} {ap2}".strip()
    except Exception as e:
        logger.error(f"Error extraeyendo nombre de INE: {e}")
        
    return None
