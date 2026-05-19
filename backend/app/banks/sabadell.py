"""
AutoTeaser - Sabadell Bank Statement Parser
Logic specific to Banco Sabadell bank statements.

Sabadell format (from example 2025.10 - SABADELL 7801.pdf):
- Account in "CUENTA: 00004337801"
- Date in "PERIODO: 01/10/2025 al 31/10/2025"
- Saldo Promedio in "Saldo promedio en el periodo $12,324.73"
- Deposits in "Depósitos $4,370,064.10" (RESUMEN GENERAL)
"""
import re


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Sabadell bank statement.

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
    # "CUENTA: 00004337801"
    match_acc = re.search(r'CUENTA:\s*(\d{8,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"sabadell{num[-4:]}"

    # ── 2. Month & Year ──
    # "PERIODO: 01/10/2025 al 31/10/2025"
    match_date = re.search(
        r'PERIODO:\s*\d{1,2}/(\d{2})/(\d{4})\s+al\s+\d{1,2}/(\d{2})/(\d{4})',
        text, re.IGNORECASE
    )
    if match_date:
        # Use end-of-period month
        m_num = match_date.group(3)
        result["year"] = match_date.group(4)
        result["month"] = meses_num.get(m_num, m_num)
    else:
        # Fallback: "FECHA Y HORA DE EXPEDICIÓN: 2025/11/01T09:23:02"
        match_date2 = re.search(r'EXPEDICI[ÓO]N:\s*(\d{4})/(\d{2})/\d{2}', text, re.IGNORECASE)
        if match_date2:
            result["year"] = match_date2.group(1)
            m_num = match_date2.group(2)
            result["month"] = meses_num.get(m_num, m_num)

    # ── 3. Average Balance (Saldo Promedio) ──
    # "Saldo promedio en el periodo $12,324.73"
    match_bal = re.search(
        r'Saldo\s+promedio\s+en\s+el\s+periodo\s*\$?([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_bal:
        match_bal = re.search(r'Saldo\s+promedio\s*\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "Depósitos $4,370,064.10" (in RESUMEN GENERAL)
    match_dep = re.search(
        r'Dep[oó]sitos\s*\$?([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
