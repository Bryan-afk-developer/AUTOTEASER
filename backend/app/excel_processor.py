"""
AutoTeaser - Excel Processor
Uses openpyxl to fill Excel templates with extracted bank statement data.

DYNAMIC BLOCK ASSIGNMENT:
- Groups all parsed data by unique account_name (e.g. "BBVA 0757", "HSBC 1352")
- Assigns each unique account to the next available block in the template
- Within each block, fills months in order by date
- No pre-assigned blocks — everything is determined at runtime
"""
import logging
import shutil
import re
from collections import defaultdict
from pathlib import Path
from openpyxl import load_workbook

logger = logging.getLogger(__name__)

# Helper to normalize and sort months chronologically
SPANISH_MONTHS = {
    'ene': 1, 'enero': 1, 'jan': 1, 'january': 1,
    'feb': 2, 'febrero': 2, 'february': 2,
    'mar': 3, 'marzo': 3, 'march': 3,
    'abr': 4, 'abril': 4, 'april': 4,
    'may': 5, 'mayo': 5, 'may': 5,
    'jun': 6, 'junio': 6, 'june': 6,
    'jul': 7, 'julio': 7, 'july': 7,
    'ago': 8, 'agosto': 8, 'august': 8, 'aug': 8,
    'sep': 9, 'septiembre': 9, 'september': 9,
    'oct': 10, 'octubre': 10, 'october': 10,
    'nov': 11, 'noviembre': 11, 'november': 11,
    'dic': 12, 'diciembre': 12, 'december': 12, 'dec': 12
}

MONTH_DISPLAY = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
}

def _get_cell_row(cell_ref: str) -> int:
    match = re.match(r"([A-Za-z]+)(\d+)", cell_ref)
    if match:
        return int(match.group(2))
    return 9999

def _get_sort_key(d):
    try:
        y = int(d.get("year", 0))
    except Exception:
        y = 0
    m_str = str(d.get("month", "")).lower().strip()[:3]
    m = SPANISH_MONTHS.get(m_str, 0)
    return (y, m)


def fill_template(template_path: str, output_path: str, data_list: list[dict], mapping: dict | None = None) -> str:
    """
    Fill an Excel template with extracted data using dynamic block assignment.
    
    Args:
        template_path: Path to the .xlsx template
        output_path: Path where the filled .xlsx will be saved
        data_list: List of dicts of extracted financial data (multiple documents)
        mapping: Dict with 'blocks' array defining available cell positions
    
    Returns:
        Path to the generated output file
    """
    # Copy template to output
    shutil.copy2(template_path, output_path)
    
    wb = load_workbook(output_path)
    
    if mapping and "blocks" in mapping:
        # ── Dynamic block assignment mode ──
        
        # 1. Select the correct sheet
        sheet_name = mapping.get("sheet_name", "Bancos")
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        elif sheet_name.upper() in wb.sheetnames:
            ws = wb[sheet_name.upper()]
        else:
            ws = wb.active
            logger.warning(f"Sheet '{sheet_name}' not found, using active sheet: {ws.title}")
        
        # 2. Group data by account_name
        accounts = defaultdict(list)
        for data in data_list:
            acct = data.get("account_name", "").strip()
            if acct:
                accounts[acct].append(data)
        
        # 3. Sort accounts alphabetically for consistent ordering
        sorted_accounts = sorted(accounts.keys())
        
        # 4. Get available blocks from mapping
        blocks = mapping["blocks"]
        
        if len(sorted_accounts) > len(blocks):
            logger.warning(
                f"More unique accounts ({len(sorted_accounts)}) than available blocks ({len(blocks)}). "
                f"Extra accounts will be skipped."
            )
        
        # 5. Assign each unique account to the next available block
        for block_idx, account_name in enumerate(sorted_accounts):
            if block_idx >= len(blocks):
                logger.warning(f"No more blocks available for account '{account_name}', skipping.")
                break
            
            block = blocks[block_idx]
            base_cell = block.get("base")
            
            # Write account name to header cell
            if base_cell:
                ws[base_cell] = account_name
                logger.info(f"Assigned block {block_idx + 1} ({base_cell}) → {account_name}")
            
            # Sort the entries chronologically by year and month index
            sorted_entries = sorted(accounts[account_name], key=_get_sort_key)
            
            # Get sorted lists of cells by their row coordinates
            sorted_dep_cells = sorted(list(block.get("depositos", {}).values()), key=_get_cell_row)
            sorted_bal_cells = sorted(list(block.get("saldo_promedio", {}).values()), key=_get_cell_row)
            
            # Fill chronological data to cell slots in order
            for data, dep_cell, bal_cell in zip(sorted_entries, sorted_dep_cells, sorted_bal_cells):
                month = data.get("month", "").lower().strip()
                deposits = data.get("deposits")
                avg_balance = data.get("average_balance")
                
                # Format month label
                year = data.get("year", "")
                year_suffix = year[-2:] if len(str(year)) >= 2 else str(year)
                
                month_idx = SPANISH_MONTHS.get(month[:3], 0)
                month_display = MONTH_DISPLAY.get(month_idx, month.capitalize())
                month_label = f"{month_display} -{year_suffix}" if year_suffix else month_display

                # Write deposits and the month label
                if deposits is not None:
                    ws[dep_cell] = deposits
                    
                    # Write the month label one column to the left
                    cell_obj = ws[dep_cell]
                    label_col = cell_obj.column - 1
                    if label_col > 0:
                        ws.cell(row=cell_obj.row, column=label_col, value=month_label)
                
                # Write average balance
                if avg_balance is not None:
                    ws[bal_cell] = avg_balance
    
    # Legacy support: old "Bancos" dict format (backwards compatible)
    elif mapping and "Bancos" in mapping:
        sheet_name = mapping.get("sheet_name", "Bancos")
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.active
        
        accounts = defaultdict(list)
        for data in data_list:
            acct = data.get("account_name", "").strip()
            if acct:
                accounts[acct].append(data)
        
        sorted_accounts = sorted(accounts.keys())
        blocks_list = list(mapping["Bancos"].values())
        
        for block_idx, account_name in enumerate(sorted_accounts):
            if block_idx >= len(blocks_list):
                break
            block = blocks_list[block_idx]
            base_cell = block.get("base")
            if base_cell:
                ws[base_cell] = account_name
            for data in accounts[account_name]:
                month = data.get("month", "").lower().strip()
                deposits = data.get("deposits")
                avg_balance = data.get("average_balance")
                if not month:
                    continue
                if deposits is not None:
                    dep_cell = block.get("depositos", {}).get(month)
                    if dep_cell:
                        ws[dep_cell] = deposits
                if avg_balance is not None:
                    bal_cell = block.get("saldo_promedio", {}).get(month)
                    if bal_cell:
                        ws[bal_cell] = avg_balance
    
    # Fallback for simple key-value mappings
    elif mapping:
        ws = wb.active
        if data_list:
            data = data_list[0]
            for key, cell_ref in mapping.items():
                if key in data:
                    ws[cell_ref] = data[key]
    
    wb.save(output_path)
    return output_path


def read_template_fields(template_path: str) -> dict:
    """
    Read an Excel template and return info about its structure.
    """
    wb = load_workbook(template_path, data_only=True)
    sheets_info = {}
    
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheets_info[sheet_name] = {
            "rows": ws.max_row,
            "cols": ws.max_column,
        }
    
    wb.close()
    return sheets_info
