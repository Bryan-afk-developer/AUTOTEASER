"""
AutoTeaser - Inbursa Bank Statement Parser
Logic specific to Inbursa bank statements.

Inbursa format (from example 2025.04 - INBURSA 0014.pdf):
- Account in "CUENTA 33002830014"
- Date in "PERIODO Del 01 Abr. 2025 al 30 Abr. 2025" or "FECHA DE CORTE 30 Abr. 2025"
- Saldo Promedio in "SALDO PROMEDIO 119,975.32"
- Deposits in "ABONOS 485,364.59"
"""
import re


def parse(text: str, pages: list[str], **kwargs) -> dict:
    """
    Parse an Inbursa bank statement.

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
    # "CUENTA 33002830014"
    match_acc = re.search(r'CUENTA\s+(\d{8,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"inbursa{num[-4:]}"

    # ── 2. Month & Year ──
    # "PERIODO Del 01 Abr. 2025 al 30 Abr. 2025"
    match_date = re.search(
        r'PERIODO\s+Del\s+\d{1,2}\s+(\w+)\.?\s+(\d{4})\s+al\s+\d{1,2}\s+(\w+)\.?\s+(\d{4})',
        text, re.IGNORECASE
    )
    if match_date:
        # Use end-of-period month
        m_raw = match_date.group(3).lower().rstrip('.')
        result["year"] = match_date.group(4)
        result["month"] = meses_map.get(m_raw, m_raw[:3])
    else:
        # Fallback: "FECHA DE CORTE 30 Abr. 2025"
        match_date2 = re.search(
            r'FECHA\s+DE\s+CORTE\s+\d{1,2}\s+(\w+)\.?\s+(\d{4})',
            text, re.IGNORECASE
        )
        if match_date2:
            m_raw = match_date2.group(1).lower().rstrip('.')
            result["year"] = match_date2.group(2)
            result["month"] = meses_map.get(m_raw, m_raw[:3])

    # ── 3. Average Balance (Saldo Promedio) ──
    # "SALDO PROMEDIO 119,975.32"
    match_bal = re.search(
        r'SALDO\s+PROMEDIO\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "ABONOS 485,364.59"
    match_dep = re.search(
        r'ABONOS\s+([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_dep:
        # Fallback: "(+) Depósitos"
        match_dep = re.search(r'\(\+\)\s*Dep[oó]sitos\s*[\$\s]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
