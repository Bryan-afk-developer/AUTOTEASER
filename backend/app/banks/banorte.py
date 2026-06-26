"""
AutoTeaser - Banorte Bank Statement Parser
Logic specific to Banorte / Enlace Negocios bank statements.

Banorte format (from example 2025.12 - BANORTE 0253.PDF):
- Account number in "ENLACE NEGOCIOS BASICA 0628135524" or "No. de Cuenta" lines
- Date in "Periodo Del 01/Diciembre/2025 al 31/Diciembre/2025" or "Fecha de corte"
- Saldo Promedio in "En el Periodo ... $ 408,895.20"
- Deposits in "+ Total de depósitos $ 2,753,695.13"
"""
import re


def parse(text: str, pages: list[str], **kwargs) -> dict:
    """
    Parse a Banorte bank statement.

    Args:
        text: Full extracted text from the PDF
        pages: List of text per page

    Returns:
        dict with account_name, month, year, deposits, average_balance
    """
    result = {
        "account_name": "",
        "month": "",
        "year": "",
        "deposits": 0.0,
        "average_balance": 0.0,
    }

    meses_map = {
        'enero': 'ene', 'febrero': 'feb', 'marzo': 'mar', 'abril': 'abr',
        'mayo': 'may', 'junio': 'jun', 'julio': 'jul', 'agosto': 'ago',
        'septiembre': 'sep', 'octubre': 'oct', 'noviembre': 'nov', 'diciembre': 'dic',
        'ene': 'ene', 'feb': 'feb', 'mar': 'mar', 'abr': 'abr',
        'may': 'may', 'jun': 'jun', 'jul': 'jul', 'ago': 'ago',
        'sep': 'sep', 'oct': 'oct', 'nov': 'nov', 'dic': 'dic',
    }

    # ── 1. Account Name ──
    # Banorte files use the CLIENT number for naming, e.g. "NO. DE CLIENTE: 08590253" → "BANORTE 0253"
    match_client = re.search(r'NO\.?\s*DE\s*CLIENTE[:\s]*(\d{6,})', text, re.IGNORECASE)
    if match_client:
        num = match_client.group(1)
        result["account_name"] = f"banorte{num[-4:]}"
    else:
        # Fallback: use the 10-digit account number
        match_acc = re.search(r'ENLACE NEGOCIOS\s+\w+\s+(\d{10})', text, re.IGNORECASE)
        if not match_acc:
            match_acc = re.search(r'(\d{10})\s+072\s+\d{3}', text)
        if match_acc:
            num = match_acc.group(1)
            result["account_name"] = f"banorte{num[-4:]}"

    # ── 2. Month & Year ──
    # "Periodo Del 01/Diciembre/2025 al 31/Diciembre/2025"
    match_date = re.search(
        r'(?:Periodo\s+Del|Fecha\s+de\s+corte)\s*[\s:]*\d{1,2}/(\w+)/(\d{4})\s+al\s+\d{1,2}/(\w+)/(\d{4})',
        text, re.IGNORECASE
    )
    if match_date:
        # Use the end-of-period month
        m_raw = match_date.group(3).lower()
        result["year"] = match_date.group(4)
        result["month"] = meses_map.get(m_raw, m_raw[:3])
    else:
        # Fallback: "Fecha de corte31/Diciembre/2025" (no space)
        match_date2 = re.search(r'Fecha\s*de\s*corte\s*(\d{1,2})[/-](\w+)[/-](\d{4})', text, re.IGNORECASE)
        if match_date2:
            m_raw = match_date2.group(2).lower()
            result["year"] = match_date2.group(3)
            result["month"] = meses_map.get(m_raw, m_raw[:3])

    # ── 3. Average Balance (Saldo Promedio) ──
    # "En el Periodo 01 Dic al 31 Dic: $ 408,895.20"
    match_bal = re.search(
        r'En\s+el\s+Periodo.*?[\$\s]+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_bal:
        # Fallback: "Saldo Promedio" followed by amount
        match_bal = re.search(r'Saldo\s+[Pp]romedio\s*[\$\s]*([\d,]+\.\d{2})', text)
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "+ Total de depósitos $ 2,753,695.13"
    match_dep = re.search(
        r'\+\s*Total\s+de\s+dep[oó]sitos\s*[\$\s]*([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_dep:
        # Fallback: "Depósitos $2,753,695.13" or "DEPÓSITOS $..."
        match_dep = re.search(r'DEP[OÓ]SITOS\s*[\$\s]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
