"""
AutoTeaser - Santander Bank Statement Parser
Logic specific to Banco Santander Mexico bank statements.

Santander format (from example 2025.11 - SANTANDER 1517-6.pdf):
- Account in "CUENTA TRADICIONAL 65-50131517-6" (last part with dash is the ID)
- Date in "PERIODO DEL 01-NOV-2025 AL 30-NOV-2025"
- Saldo Promedio in "Saldo promedio 69,389.75"
- Deposits in "+Dep(cid:243)sitos 9,517,037.51" or "+Depósitos"
"""
import re


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Santander bank statement.

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
        'jan': 'ene',
    }

    # ── 1. Account Name ──
    # "CUENTA TRADICIONAL 65-50131517-6"
    # The account identifier is the last segment: "1517-6"
    match_acc = re.search(
        r'CUENTA\s+TRADICIONAL\s+(\d{2}-\d{8,}-\d)',
        text, re.IGNORECASE
    )
    if match_acc:
        full_num = match_acc.group(1)  # e.g. "65-50131517-6"
        # Extract the meaningful part: last 4 digits before dash + dash + last digit
        # "65-50131517-6" → "1517-6"
        parts = full_num.split('-')
        if len(parts) == 3:
            short = parts[1][-4:] + '-' + parts[2]  # "1517-6"
        else:
            short = full_num[-6:]
        result["account_name"] = f"santander{short}"
    else:
        # Fallback: any Santander-style account number
        match_acc2 = re.search(r'No\.?\s*de\s*[Cc]uenta[:\s]*(\S+)', text)
        if match_acc2:
            result["account_name"] = f"santander{match_acc2.group(1)[-6:]}"

    # ── 2. Month & Year ──
    # "PERIODO DEL 01-NOV-2025 AL 30-NOV-2025"
    match_date = re.search(
        r'PERIODO\s+DEL\s+\d{1,2}-([A-Z]{3})-(\d{4})\s+AL\s+\d{1,2}-([A-Z]{3})-(\d{4})',
        text, re.IGNORECASE
    )
    if match_date:
        m_raw = match_date.group(3).lower()
        result["year"] = match_date.group(4)
        result["month"] = meses_map.get(m_raw, m_raw)
    else:
        # Fallback: "CORTE AL 30-NOV-2025"
        match_date2 = re.search(r'CORTE\s+AL\s+\d{1,2}-([A-Z]{3})-(\d{4})', text, re.IGNORECASE)
        if match_date2:
            m_raw = match_date2.group(1).lower()
            result["year"] = match_date2.group(2)
            result["month"] = meses_map.get(m_raw, m_raw)

    # ── 3. Average Balance (Saldo Promedio) ──
    # "Saldo promedio 69,389.75"
    # Be careful: Santander has "Saldo promedio" for both checking and investment accounts.
    # We want the one for CUENTA TRADICIONAL (first occurrence)
    match_bal = re.search(
        r'Saldo\s+promedio\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "+Dep(cid:243)sitos 9,517,037.51" (Santander uses (cid:243) for ó)
    # or "+Depósitos 9,517,037.51"
    match_dep = re.search(
        r'\+\s*Dep(?:\(cid:\d+\)|[oó])sitos\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_dep:
        # Fallback: "Abonos $9,517,037.51"
        match_dep = re.search(r'Abonos\s*\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
