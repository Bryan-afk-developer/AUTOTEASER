"""
AutoTeaser - BBVA Bank Statement Parser
Logic specific to BBVA Mexico bank statements.

BBVA format (from example 2025.11 - BBVA 0757.pdf):
- Account in "No. de Cuenta 0169920757"
- Date in "Periodo DEL 01/11/2025 AL 30/11/2025"
- Saldo Promedio in "Saldo Promedio 2,603,512.56"
- Deposits in "Depósitos / Abonos (+) 456 76,778,579.95"
  (the number after (+) is the transaction count, the big number is the total)
"""
import re


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a BBVA bank statement.

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

    meses_num = {
        '01': 'ene', '02': 'feb', '03': 'mar', '04': 'abr',
        '05': 'may', '06': 'jun', '07': 'jul', '08': 'ago',
        '09': 'sep', '10': 'oct', '11': 'nov', '12': 'dic',
    }

    # ── 1. Account Name ──
    # "No. de Cuenta 0169920757"
    match_acc = re.search(r'No\.?\s*de\s*Cuenta\s+(\d{8,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"BBVA {num[-4:]}"

    # ── 2. Month & Year ──
    # "Periodo DEL 01/11/2025 AL 30/11/2025"
    # or "DEL 01/NOV/2025 AL 30/NOV/2025"
    match_date = re.search(
        r'(?:Periodo\s+)?DEL\s+\d{1,2}/(\d{2})/(\d{4})\s+AL\s+\d{1,2}/(\d{2})/(\d{4})',
        text, re.IGNORECASE
    )
    if match_date:
        # Use end-of-period month
        m_num = match_date.group(3)
        result["year"] = match_date.group(4)
        result["month"] = meses_num.get(m_num, m_num)
    else:
        # Fallback: "Fecha de Corte 30/11/2025"
        match_date2 = re.search(
            r'Fecha\s+de\s+Corte\s+\d{1,2}/(\d{2})/(\d{4})',
            text, re.IGNORECASE
        )
        if match_date2:
            m_num = match_date2.group(1)
            result["year"] = match_date2.group(2)
            result["month"] = meses_num.get(m_num, m_num)

    # ── 3. Average Balance (Saldo Promedio) ──
    # "Saldo Promedio 2,603,512.56"
    # Be careful: there are multiple "Saldo Promedio" lines. We want the first one
    # (the main account one, not "Saldo Promedio Gravable" or "Saldo Promedio Mínimo")
    match_bal = re.search(
        r'Saldo\s+Promedio\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "Depósitos / Abonos (+) 456 76,778,579.95"
    # Pattern: "Depósitos / Abonos (+)" then transaction count then amount
    match_dep = re.search(
        r'Dep[oó]sitos\s*/\s*Abonos\s*\(\+\)\s*\d+\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_dep:
        # Fallback: just "Depósitos" or "Abonos" followed by amount
        match_dep = re.search(
            r'(?:Dep[oó]sitos|Abonos)\s*(?:\(\+\))?\s*\d*\s*([\d,]+\.\d{2})',
            text, re.IGNORECASE
        )
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
