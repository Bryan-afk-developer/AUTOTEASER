import fitz  # PyMuPDF
import re
import logging

logger = logging.getLogger(__name__)

def extract_csf_info(file_bytes: bytes, filename: str) -> dict:
    """
    Lee un PDF de Constancia de Situación Fiscal y extrae:
    - nombre: Nombre del contribuyente (persona física o moral)
    - rfc: RFC del contribuyente
    - fecha: Fecha de emisión de la CSF (AAAA.MM.DD)
    - location: Dirección (legacy, se mantiene por compatibilidad)
    """
    result = {"location": "Ubicacion no detectada", "rfc": None, "nombre": None, "fecha": None}
    
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
        rfc_match = re.search(r'([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})', text)
        if rfc_match:
            result["rfc"] = rfc_match.group(1)
        
        # ── Extraer Nombre del Contribuyente ──
        # En la CSF el nombre aparece después de etiquetas como:
        # "Nombre (s)" / "Primer Apellido" / "Segundo Apellido" (persona física)
        # o "Denominación/Razón Social" (persona moral)
        
        # Persona moral: Denominación/Razón Social
        razon_match = re.search(
            r'Denominaci[oó]n[/ ]+Raz[oó]n Social[:\s]*([^\n]+)',
            text, re.IGNORECASE
        )
        if razon_match:
            nombre = razon_match.group(1).strip()
            if nombre:
                result["nombre"] = nombre.upper()
        
        # Persona física: combinamos Nombre(s) + Primer Apellido + Segundo Apellido
        if not result["nombre"]:
            nombre_match = re.search(r'Nombre \(s\)[:\s]*([^\n]+)', text, re.IGNORECASE)
            ap1_match   = re.search(r'Primer Apellido[:\s]*([^\n]+)', text, re.IGNORECASE)
            ap2_match   = re.search(r'Segundo Apellido[:\s]*([^\n]+)', text, re.IGNORECASE)

            logger.info(f"[CSF] nombre_match={nombre_match and nombre_match.group(1)}")
            logger.info(f"[CSF] ap1_match={ap1_match and ap1_match.group(1)}")
            logger.info(f"[CSF] ap2_match={ap2_match and ap2_match.group(1)}")

            partes = []
            if ap1_match: partes.append(ap1_match.group(1).strip())
            if ap2_match: partes.append(ap2_match.group(1).strip())
            if nombre_match: partes.append(nombre_match.group(1).strip())

            if partes:
                result["nombre"] = " ".join(p for p in partes if p).upper()

        # Fallback: buscar patrón RFC y tomar el nombre que viene debajo
        if not result["nombre"]:
            rfc_line_match = re.search(r'RFC[:\s]*[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\s*\n([^\n]+)', text)
            if rfc_line_match:
                result["nombre"] = rfc_line_match.group(1).strip().upper()

        logger.info(f"[CSF] nombre extraido: {result.get('nombre')}")

        # ── Extraer Fecha de Emisión ──
        # Buscar patrón "Fecha de emisión: DD/MM/AAAA" o "DD de mes de AAAA"
        fecha_match = re.search(
            r'Fecha de [Ee]misi[oó]n[:\s]*(\d{2})[/-](\d{2})[/-](\d{4})',
            text
        )
        if fecha_match:
            d, m, y = fecha_match.group(1), fecha_match.group(2), fecha_match.group(3)
            result["fecha"] = f"{y}.{m}.{d}"
        
        if not result["fecha"]:
            # Formato alternativo: DD/MM/AAAA suelto en texto
            fecha_match2 = re.search(r'\b(\d{2})[/-](\d{2})[/-](\d{4})\b', text)
            if fecha_match2:
                d, m, y = fecha_match2.group(1), fecha_match2.group(2), fecha_match2.group(3)
                result["fecha"] = f"{y}.{m}.{d}"

        if not result["fecha"]:
            # Formato “DD de mes de AAAA”
            meses = {'enero':'01','febrero':'02','marzo':'03','abril':'04','mayo':'05','junio':'06',
                     'julio':'07','agosto':'08','septiembre':'09','octubre':'10','noviembre':'11','diciembre':'12'}
            fecha_match3 = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', text, re.IGNORECASE)
            if fecha_match3:
                d = fecha_match3.group(1).zfill(2)
                m = meses.get(fecha_match3.group(2).lower(), '00')
                y = fecha_match3.group(3)
                result["fecha"] = f"{y}.{m}.{d}"

        logger.info(f"[CSF] fecha extraida: {result.get('fecha')}")

        # ── Legacy: también guardamos la ubicación por si algo la usa ──
        domicilio_section = _extract_domicilio_section(text)
        if domicilio_section:
            tipo_vial = _extract_field(domicilio_section, r'Tipo de Vialidad[:\s]*([^\n]+)')
            nom_vial = _extract_multiline_field(domicilio_section, r'Nombre de la Vialidad[:\s]*([^\n]+)', r'N[úu]mero Exterior')
            no_ext = _extract_field(domicilio_section, r'N[úu]mero Exterior[:\s]*([^\n]+)')
            no_int = _extract_field(domicilio_section, r'N[úu]mero Interior[:\s]*([^\n]+)')
            colonia = _extract_multiline_field(domicilio_section, r'Nombre de la Colonia[:\s]*([^\n]+)', r'Nombre de la Localidad')
            cp = _extract_field(domicilio_section, r'C[óo]digo Postal[:\s]*(\d{5})')
            municipio = _extract_multiline_field(domicilio_section, r'Nombre del Municipio o Demarcaci[óo]n Territorial[:\s]*([^\n]+)', r'Nombre de la Entidad')
            estado = _extract_field(domicilio_section, r'Nombre de la Entidad Federativa[:\s]*([^\n]+)')
            
            partes_calle = []
            calle_str = f"{tipo_vial} {nom_vial}".strip()
            if calle_str:
                # Capitalizar si está todo en mayúsculas para mejor lectura
                partes_calle.append(calle_str.title() if calle_str.isupper() else calle_str)
            if no_ext:
                partes_calle.append(f"No. {no_ext}")
            if no_int:
                partes_calle.append(f"Int. {no_int}")
            
            direccion_base = " ".join(partes_calle)
            
            detalles = []
            if direccion_base:
                detalles.append(direccion_base)
            if colonia:
                detalles.append(f"Colonia {colonia.title() if colonia.isupper() else colonia}")
            if cp:
                detalles.append(f"C.P. {cp}")
            if municipio:
                detalles.append(municipio.title() if municipio.isupper() else municipio)
            if estado:
                detalles.append(estado.title() if estado.isupper() else estado)
            
            if detalles:
                result["location"] = ", ".join(detalles) + "."

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
