import fitz
import re
import logging

logger = logging.getLogger(__name__)

def is_sat_pdf_altered(pdf_bytes: bytes) -> tuple[bool, str]:
    """
    Verifica si un PDF del SAT (Declaración, Acuse, etc) ha sido alterado.
    Devuelve (True, "Motivo") si es sospechoso, (False, "") si parece legítimo.
    """
    try:
        # 1. Checar marcadores de actualización incremental (%%EOF)
        # Los PDF generados limpios por el SAT suelen tener 1 solo marcador %%EOF o 2 si incluyen XMP al final.
        # Editores como Acrobat a menudo añaden más marcadores de actualización incremental.
        eof_count = pdf_bytes.count(b'%%EOF')
        if eof_count > 2:
            return True, f"Estructura PDF modificada (múltiples actualizaciones, {eof_count} EOFs detectados)."

        # 2. Analizar metadatos internos con PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        meta = doc.metadata
        creator = (meta.get("creator") or "").lower()
        producer = (meta.get("producer") or "").lower()
        
        # Herramientas sospechosas conocidas
        suspicious_tools = ['ilovepdf', 'acrobat', 'sejda', 'canva', 'foxit', 'nitro', 'pdf24', 'smallpdf', 'word', 'microsoft']
        
        for tool in suspicious_tools:
            if tool in creator or tool in producer:
                return True, f"Metadatos alterados por editor no oficial: {tool.title()} detectado."
                
        # Los documentos del SAT originales suelen ser de Apache FOP o PDFium, 
        # o venir con metadatos completamente en blanco (como declaraciones complementarias antiguas).
        
        # 3. Analizar XMP Metadata buscando discrepancias en fechas
        try:
            xmp = doc.get_xml_metadata()
            if xmp:
                # Extraer CreateDate y MetadataDate/ModifyDate si existen
                create_match = re.search(r'<xmp:CreateDate>(.*?)</xmp:CreateDate>', xmp)
                meta_match = re.search(r'<xmp:MetadataDate>(.*?)</xmp:MetadataDate>', xmp)
                mod_match = re.search(r'<xmp:ModifyDate>(.*?)</xmp:ModifyDate>', xmp)
                
                create_date = create_match.group(1) if create_match else None
                meta_date = meta_match.group(1) if meta_match else None
                mod_date = mod_match.group(1) if mod_match else None
                
                # Si existe una fecha de modificación y no coincide EXACTAMENTE con la de creación (cuando ambas existen)
                if create_date:
                    if meta_date and meta_date != create_date:
                        return True, "Discrepancia en fechas XMP (El documento fue reguardado después de su creación)."
                    if mod_date and mod_date != create_date:
                        return True, "Discrepancia en fechas XMP (El documento fue modificado después de su creación)."
        except Exception as e_xmp:
            logger.warning(f"Error analizando XMP: {e_xmp}")

        # Si pasa todas las pruebas, se considera legítimo
        return False, ""

    except Exception as e:
        logger.error(f"Error procesando PDF para verificación anti-fraude: {e}")
        # En caso de error de lectura, es mejor no bloquear, o asuminr riesgo. Optamos por no bloquear.
        return False, f"No se pudo verificar: {str(e)}"
