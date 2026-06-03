"""
AutoTeaser - SAT Declaración Anual Parser
Detects and parses 'DECLARACIÓN DEL EJERCICIO' del SAT (ISR Personas Morales).

Señales de identificación:
  - Contiene: "DECLARACIÓN DEL EJERCICIO"
  - Contiene: "ISR PERSONAS MORALES"
  - Contiene: "Ejercicio: XXXX"
  - NO contiene: "ACUSE DE RECIBO" (para diferenciarlo del acuse)
"""
import re


KEYWORDS = [
    "DECLARACIÓN DEL EJERCICIO",
    "ISR PERSONAS MORALES",
]


def matches(text: str) -> bool:
    """Returns True if the PDF text looks like a SAT Declaración del Ejercicio."""
    text_upper = text.upper()
    return (
        "DECLARACI" in text_upper
        and ("DEL EJERCICIO" in text_upper or "ISR PERSONAS MORALES" in text_upper)
        and "ACUSE DE RECIBO" not in text_upper
    )


def parse(text: str) -> dict:
    """
    Extracts year from a Declaración del Ejercicio del SAT.

    Returns:
        dict with: tipo, year
    """
    result = {
        "tipo": "declaracion",
        "year": None,
    }

    # "Período de la declaración: Del Ejercicio Ejercicio: 2025"
    match = re.search(r'Ejercicio[:\s]+(\d{4})', text, re.IGNORECASE)
    if match:
        result["year"] = match.group(1)
    else:
        match2 = re.search(r'Per[ií]odo.*?(\d{4})', text, re.IGNORECASE)
        if match2:
            result["year"] = match2.group(1)
        else:
            # Fallback: look for a 4-digit year
            years = re.findall(r'\b(20\d{2})\b', text)
            if years:
                from collections import Counter
                result["year"] = Counter(years).most_common(1)[0][0]

    return result
