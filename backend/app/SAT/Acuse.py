"""
AutoTeaser - SAT Acuse de Recibo Parser
Detects and parses 'ACUSE DE RECIBO' de Declaración Anual del SAT.

Señales de identificación:
  - Contiene: "ACUSE DE RECIBO"
  - Contiene: "Declaración Anual"
  - Contiene: "Ejercicio: XXXX"
"""
import re


KEYWORDS = [
    "ACUSE DE RECIBO",
    "Declaración Anual de Personas",
]


def matches(text: str) -> bool:
    """Returns True if the PDF text looks like a SAT Acuse de Recibo."""
    text_upper = text.upper()
    return (
        "ACUSE DE RECIBO" in text_upper
        and ("DECLARACI" in text_upper)
        and ("EJERCICIO" in text_upper or "DEL EJERCICIO" in text_upper)
    )


def parse(text: str) -> dict:
    """
    Extracts year from an Acuse de Recibo del SAT.

    Returns:
        dict with: tipo, year
    """
    result = {
        "tipo": "acuse",
        "year": None,
    }

    # Look for "Ejercicio: 2025" or "Ejercicio Ejercicio: 2025"
    match = re.search(r'Ejercicio[:\s]+(\d{4})', text, re.IGNORECASE)
    if match:
        result["year"] = match.group(1)
    else:
        # Fallback: look for "Del Ejercicio Ejercicio: 2025"
        match2 = re.search(r'Del\s+Ejercicio\s+Ejercicio[:\s]+(\d{4})', text, re.IGNORECASE)
        if match2:
            result["year"] = match2.group(1)
        else:
            # Fallback: look for a 4-digit year that looks like a fiscal year
            years = re.findall(r'\b(20\d{2})\b', text)
            if years:
                # Take the most common year
                from collections import Counter
                result["year"] = Counter(years).most_common(1)[0][0]

    return result
