"""
AutoTeaser - Banamex (Citibanamex) Bank Statement Parser
Logic specific to Banamex bank statements.
"""
import re


def parse(text: str, pages: list[str]) -> dict:
    """
    Parse a Banamex bank statement.
    
    Args:
        text: Full extracted text from the PDF
        pages: List of text per page
    
    Returns:
        dict with extracted financial data:
        {
            "account_name": str,
            "month": str,
            "year": str,
            "deposits": float,
            "average_balance": float
        }
    """
    result = {
        "account_name": "",
        "month": "",
        "year": "",
        "deposits": 0.0,
        "average_balance": 0.0
    }

    # 1. Account Name
    # Look for CONTRATO 7703152093 or similar
    match_acc = re.search(r'(?:CONTRATO|Cuenta de Cheques[^0-9]+)\s*(\d{4,})', text, re.IGNORECASE)
    if match_acc:
        num = match_acc.group(1)
        result["account_name"] = f"banamex{num[-4:]}"

    # 2. Month & Year
    meses_map = {
        'enero': 'ene', 'febrero': 'feb', 'marzo': 'mar', 'abril': 'abr',
        'mayo': 'may', 'junio': 'jun', 'julio': 'jul', 'agosto': 'ago',
        'septiembre': 'sep', 'octubre': 'oct', 'noviembre': 'nov', 'diciembre': 'dic',
        'ene': 'ene', 'feb': 'feb', 'mar': 'mar', 'abr': 'abr',
        'may': 'may', 'jun': 'jun', 'jul': 'jul', 'ago': 'ago',
        'sep': 'sep', 'oct': 'oct', 'nov': 'nov', 'dic': 'dic'
    }

    match_date = re.search(r'ESTADO DE CUENTA AL \d+ DE (\w+) DE (\d{4})', text, re.IGNORECASE)
    if not match_date:
        match_date = re.search(r'AL \d+/(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)/(\d{4})', text, re.IGNORECASE)

    if match_date:
        m_raw = match_date.group(1).lower()
        result["year"] = match_date.group(2)
        result["month"] = meses_map.get(m_raw, m_raw[:3])

    # 3. Average Balance (Saldo Promedio)
    match_bal = re.search(r'Saldo Promedio\s*[\$\s]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if match_bal:
        result["average_balance"] = float(match_bal.group(1).replace(',', ''))

    # 4. Deposits (RESUMEN POR MEDIOS DE ACCESO)
    # Primary strategy: sum up all deposit lines in RESUMEN POR MEDIOS DE ACCESO
    section_match = re.search(
        r'RESUMEN POR MEDIOS DE ACCESO\s+RETIROS\s+DEPOSITOS(.*?)(?:DETALLE DE OPERACIONES|RESUMEN GENERAL|$)',
        text, re.DOTALL | re.IGNORECASE
    )
    
    total_dep = 0.0
    if section_match:
        lines = section_match.group(1).strip().split('\n')
        for line in lines:
            amounts = re.findall(r'\$([\d,]+\.\d{2})', line)
            if amounts:
                # The last dollar amount on the line is DEPOSITOS
                dep_val = float(amounts[-1].replace(',', ''))
                total_dep += dep_val
    
    # Fallback strategy: look for "( + ) 45 Depósitos $5,049,519.52" in the summary
    if total_dep == 0.0:
        match_dep_fb = re.search(r'\(\s*\+\s*\)\s*\d*\s*Dep[oó]sitos\s*[\$\s]*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if match_dep_fb:
            total_dep = float(match_dep_fb.group(1).replace(',', ''))

    result["deposits"] = total_dep

    return result
