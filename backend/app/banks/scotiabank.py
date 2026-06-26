"""
AutoTeaser - Scotiabank Bank Statement Parser
Logic specific to Scotiabank bank statements.

Scotiabank format (from example 2025.03 - SCOTIABANK 6212.pdf):
- Account in "Cuenta 17001166212"
- Date in "Fechadecorte 31-MAR-25" or "Periodo 03-MAR-25/31-MAR-25"
- Saldo Promedio in "Sdo. Prom. (1) de la Cta. MARZO $845.47"
- Deposits in "(+)Depósitos $0.00" (resumen section)
"""
import re


def parse(text: str, pages: list[str], **kwargs) -> dict:
    """
    Parse a Scotiabank bank statement.

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

    meses_3_map = {
        'ene': 'ene', 'feb': 'feb', 'mar': 'mar', 'abr': 'abr',
        'may': 'may', 'jun': 'jun', 'jul': 'jul', 'ago': 'ago',
        'sep': 'sep', 'oct': 'oct', 'nov': 'nov', 'dic': 'dic',
    }

    # ── 1. Account Name ──
    # "Cuenta 17001166212"
    match_acc = re.search(r'Cuenta\s+(\d{8,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"scotiabank{num[-4:]}"

    # ── 2. Month & Year ──
    # "Fechadecorte 31-MAR-25" (no spaces, Scotiabank format)
    match_date = re.search(
        r'Fecha\s*de\s*corte\s*(\d{1,2})-([A-Z]{3})-(\d{2,4})',
        text, re.IGNORECASE
    )
    if match_date:
        m_raw = match_date.group(2).lower()
        yr = match_date.group(3)
        if len(yr) == 2:
            yr = "20" + yr
        result["year"] = yr
        result["month"] = meses_3_map.get(m_raw, m_raw)
    else:
        # Fallback: "Periodo 03-MAR-25/31-MAR-25"
        match_date2 = re.search(
            r'Periodo\s+\d{1,2}-([A-Z]{3})-(\d{2,4})/\d{1,2}-([A-Z]{3})-(\d{2,4})',
            text, re.IGNORECASE
        )
        if match_date2:
            m_raw = match_date2.group(3).lower()
            yr = match_date2.group(4)
            if len(yr) == 2:
                yr = "20" + yr
            result["year"] = yr
            result["month"] = meses_3_map.get(m_raw, m_raw)

    # ── 3. Average Balance (Saldo Promedio) ──
    # "Sdo. Prom. (1) de la Cta. MARZO $845.47"
    # or "Sdo.Prom.M\u00edn.requeridoencuenta" (different field, skip that)
    match_bal = re.search(
        r'Sdo\.?\s*Prom\.?\s*\(1\)\s*de\s*la\s*Cta\.?\s*\w+\s*\$?([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_bal:
        # Fallback: simpler "Saldo Promedio" pattern
        match_bal = re.search(
            r'Saldo\s*Promedio\s*[\$\s]*([\d,]+\.\d{2})',
            text, re.IGNORECASE
        )
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # ── 4. Deposits ──
    # "(+)Depósitos $0.00" (may have no space)
    match_dep = re.search(
        r'\(\+\)\s*Dep[oó]sitos\s*\$?([\d,]+\.\d{2})',
        text, re.IGNORECASE
    )
    if not match_dep:
        # Fallback: "Depósitos" standalone
        match_dep = re.search(r'Dep[oó]sitos\s*\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
    if match_dep:
        result["deposits"] = float(match_dep.group(1).replace(',', ''))

    return result
