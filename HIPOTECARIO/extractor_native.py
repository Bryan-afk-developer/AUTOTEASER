import fitz

def extract_native_text(pdf_path: str) -> str:
    """
    Extrae texto de un PDF preservando en la medida de lo posible 
    el orden visual (líneas de izquierda a derecha, de arriba a abajo).
    Retorna el texto consolidado de todo el documento.
    """
    doc = fitz.open(pdf_path)
    full_text = ""
    
    for page in doc:
        # Extraer bloques de texto para mantener un mejor orden
        blocks = page.get_text("blocks")
        # Sort blocks by vertical position, then horizontal
        blocks.sort(key=lambda b: (b[1], b[0]))
        
        for block in blocks:
            # block[4] contiene el texto del bloque
            if block[4]:
                full_text += block[4] + "\n"
                
    doc.close()
    return full_text.strip()
