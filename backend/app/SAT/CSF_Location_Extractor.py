import fitz  # PyMuPDF
import re
import logging

logger = logging.getLogger(__name__)

def extract_csf_info(file_bytes: bytes, filename: str) -> dict:
    """
    Lee un PDF de Constancia de Situación Fiscal y extrae la ubicación y el RFC.
    Funciona tanto para Personas Morales como Personas Físicas.
    Devuelve un diccionario: {"location": "Colonia, Municipio...", "rfc": "ABC123456789"}
    """
    result = {"location": "Ubicacion no detectada", "rfc": None}
    
    try:
        if not filename.lower().endswith('.pdf'):
            return result

        doc = fitz.open("pdf", file_bytes)
        if len(doc) == 0:
            doc.close()
            return result
            
        # Revisamos las primeras 3 páginas
        text = ""
        for i in range(min(3, len(doc))):
            page = doc.load_page(i)
            text += page.get_text()
            
        doc.close()
        
        # ── Extraer RFC ──
        # El RFC en México tiene formato de 3 o 4 letras, 6 números y 3 caracteres alfanuméricos.
        # Generalmente viene precedido por "Registro Federal de Contribuyentes" o simplemente "RFC"
        rfc_match = re.search(r'([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})', text)
        if rfc_match:
            result["rfc"] = rfc_match.group(1)
        
        # ── Paso 1: Aislar la sección "Datos del domicilio registrado" ──
        domicilio_section = _extract_domicilio_section(text)
        
        if not domicilio_section:
            logger.warning("CSF: No se encontró la sección 'Datos del domicilio registrado'")
            return result
        
        # ── Paso 2: Extraer campos específicos de esa sección ──
        cp = _extract_field(domicilio_section, r'C[óo]digo Postal[:\s]*(\d{5})')
        vialidad = _extract_field(domicilio_section, r'Nombre de Vialidad[:\s]*([^\n]+)')
        num_ext = _extract_field(domicilio_section, r'N[úu]mero Exterior[:\s]*([^\n]+)')
        colonia = _extract_field(domicilio_section, r'Nombre de la Colonia[:\s]*([^\n]+)')
        municipio = _extract_multiline_field(domicilio_section, r'Nombre del Municipio o Demarcaci[óo]n Territorial[:\s]*([^\n]+)', r'Nombre de la Entidad')
        estado = _extract_field(domicilio_section, r'Nombre de la Entidad Federativa[:\s]*([^\n]+)')
        
        if not (municipio and estado and cp):
            logger.warning(f"CSF: Campos incompletos - CP:{cp}, Municipio:{municipio}, Estado:{estado}")
            return result
        
        # Construir la ubicación con calle incluida
        parts = []
        if vialidad:
            calle = vialidad
            if num_ext:
                calle += f" #{num_ext}"
            parts.append(calle)
        if colonia:
            parts.append(colonia)
        parts.append(municipio)
        parts.append(estado)
        parts.append(cp)
        
        location = ", ".join(parts)
        
        # Limpiar el string para nombre de archivo
        location = re.sub(r'[<>:"/\\|?*]', '', location)
        location = " ".join(location.split())
        
        # Formatear a Title Case para que coincida visualmente con los Comprobantes de Domicilio
        def smart_title(s):
            # Convierte a minúsculas y luego capitaliza cada palabra
            words = s.lower().split()
            title_words = [w.capitalize() if not re.match(r'^c\.?p\.?$', w, re.IGNORECASE) else 'CP' for w in words]
            return " ".join(title_words)
            
        location = smart_title(location)
        location = f"SAT - {location}"
        
        if len(location) > 120:
            location = location[:117] + "..."
            
        result["location"] = location
        return result
        
    except Exception as e:
        logger.error(f"Error extrayendo información de CSF: {e}")
        return result


def _extract_domicilio_section(text: str) -> str:
    """
    Aísla la sección 'Datos del domicilio registrado' del texto completo de la CSF.
    Busca desde esa etiqueta hasta la siguiente sección conocida.
    """
    # Buscar el inicio de la sección de domicilio
    match = re.search(r'Datos del domicilio registrado\s*\n?', text, re.IGNORECASE)
    if not match:
        return ""
    
    start = match.end()
    
    # Buscar el fin de la sección (siguiente sección conocida)
    end_patterns = [
        r'Actividades Econ[óo]micas',
        r'Reg[ií]menes\b',
        r'Obligaciones\b',
        r'P[áa]gina\s+\[\d+\]',
    ]
    
    end = len(text)
    for pattern in end_patterns:
        end_match = re.search(pattern, text[start:], re.IGNORECASE)
        if end_match and (start + end_match.start()) < end:
            end = start + end_match.start()
    
    return text[start:end]


def _extract_field(section: str, pattern: str) -> str:
    """Extrae un campo simple de la sección de domicilio."""
    match = re.search(pattern, section, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_multiline_field(section: str, pattern: str, stop_pattern: str) -> str:
    """
    Extrae un campo que puede estar partido en dos líneas.
    Por ejemplo: 'Nombre del Municipio o Demarcación Territorial: ATIZAPAN DE\nZARAGOZA'
    """
    match = re.search(pattern, section, re.IGNORECASE)
    if not match:
        return ""
    
    value = match.group(1).strip()
    
    # Verificar si el valor continúa en la siguiente línea
    remaining = section[match.end():]
    lines = remaining.split('\n')
    # Buscar la primera línea no vacía después del match
    for line in lines:
        next_line = line.strip()
        if not next_line:
            continue
        # Si la siguiente línea NO es otra etiqueta conocida, es continuación
        if not re.search(stop_pattern, next_line, re.IGNORECASE) and not re.search(r'[\w\s]+:', next_line):
            value += " " + next_line
        break
    
    return value
