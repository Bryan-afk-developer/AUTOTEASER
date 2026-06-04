"""
AutoTeaser - Opinión de Cumplimiento Parser

Detects whether a SAT Opinión del Cumplimiento is POSITIVO or NEGATIVO.

Returns:
  {
    "es_opinion_cumplimiento": True | False,
    "sentido": "POSITIVO" | "NEGATIVO" | None
  }
"""
import re


MARKERS = [
    "opinión del cumplimiento de obligaciones fiscales",
    "opinion del cumplimiento de obligaciones fiscales",
    "opini\u00f3n de cumplimiento",
    "cumplimiento de obligaciones fiscales",
]


def matches(text: str) -> bool:
    """Returns True if the text looks like an Opinión de Cumplimiento."""
    upper = text.upper()
    return any(m.upper() in upper for m in MARKERS)


def parse(text: str) -> dict:
    """
    Extracts the sentido (POSITIVO / NEGATIVO) from the document.
    """
    result = {
        "es_opinion_cumplimiento": True,
        "sentido": None,
    }

    upper = text.upper()

    if "POSITIVO" in upper:
        result["sentido"] = "POSITIVO"
    elif "NEGATIVO" in upper:
        result["sentido"] = "NEGATIVO"

    return result
