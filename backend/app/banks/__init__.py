"""
AutoTeaser - Bank Parsers Package
Each file in this package handles the parsing logic for a specific bank.
"""

from app.banks import hsbc, bbva, banorte, santander, scotiabank, banamex, inbursa, sabadell

# Registry: bank key → parser module
BANK_PARSERS = {
    "hsbc": hsbc,
    "bbva": bbva,
    "banorte": banorte,
    "santander": santander,
    "scotiabank": scotiabank,
    "banamex": banamex,
    "inbursa": inbursa,
    "sabadell": sabadell,
}


def get_parser(bank_key: str):
    """
    Get the parser module for a given bank key.
    Returns the module or None if not found.
    """
    return BANK_PARSERS.get(bank_key)
