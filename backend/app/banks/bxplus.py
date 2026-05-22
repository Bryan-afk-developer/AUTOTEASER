"""
AutoTeaser - BX+ (Banco Ve por Más) Bank Statement Parser
Logic specific to BX+ / Banco Ve por Más bank statements.
"""
import re


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a BX+ bank statement.

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
    # "Num Cuenta" or "Cuenta a la Vista"
    # Example: Num Cuenta: 00000184991 or Cuenta a la Vista 00000184991
    match_acc = re.search(r'(?:Num\s+Cuenta|Cuenta\s+a\s+la\s+Vista)[\s:]*(\d{5,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"bxplus{num[-4:]}"

    # ── 2. Month & Year ──
    # "Periodo: 01-02-2026 28-02-2026"
    # or "Fecha de Corte 28-02-2026"
    match_period = re.search(
        r'Periodo[:\s]*\d{2}[-/]\d{2}[-/]\d{4}\s+\d{2}[-/](\d{2})[-/](\d{4})',
        text, re.IGNORECASE
    )
    if match_period:
        m_num = match_period.group(1)
        result["year"] = match_period.group(2)
        result["month"] = meses_num.get(m_num, m_num)
    else:
        match_corte = re.search(
            r'Fecha\s+de\s+Corte[:\s]*\d{2}[-/](\d{2})[-/](\d{4})',
            text, re.IGNORECASE
        )
        if match_corte:
            m_num = match_corte.group(1)
            result["year"] = match_corte.group(2)
            result["month"] = meses_num.get(m_num, m_num)

    # ── 3. Average Balance (Saldo Promedio) ──
    # "SALDO PROMEDIO" in the account summary
    match_bal = re.search(
        r'SALDO\s+PROMEDIO[:\s]*\$?\s*([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Total Deposits ──
    # "Depósitos" or "Abonos" in the summary table
    match_dep = re.search(
        r'(?:Total\s+de\s+)?(?:Dep[oó]sitos|Abonos)[:\s]*\$?\s*([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
