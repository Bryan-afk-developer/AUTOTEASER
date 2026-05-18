"""
AutoTeaser - Excel Processor
Uses openpyxl to fill Excel templates with extracted bank statement data.
"""
import shutil
from pathlib import Path
from openpyxl import load_workbook


def fill_template(template_path: str, output_path: str, data_list: list[dict], mapping: dict | None = None) -> str:
    """
    Fill an Excel template with extracted data using a coordinate mapping.
    
    Args:
        template_path: Path to the .xlsx template
        output_path: Path where the filled .xlsx will be saved
        data_list: List of dicts of extracted financial data (multiple documents)
        mapping: Dict mapping data keys to Excel cell coordinates
    
    Returns:
        Path to the generated output file
    """
    # Copy template to output
    shutil.copy2(template_path, output_path)
    
    wb = load_workbook(output_path)
    
    if mapping and "Bancos" in mapping:
        # Check if the template has a sheet named 'Bancos' (or similar)
        if "Bancos" in wb.sheetnames:
            ws = wb["Bancos"]
        elif "BANCOS" in wb.sheetnames:
            ws = wb["BANCOS"]
        else:
            ws = wb.active
            
        for data in data_list:
            account_name = data.get("account_name")
            month = data.get("month", "").lower()
            deposits = data.get("deposits")
            avg_balance = data.get("average_balance")

            if not account_name:
                continue

            # Find which bank block matches our account_name, OR find the first available block
            target_bank_info = None
            empty_bank_info = None
            
            for b_key, b_info in mapping["Bancos"].items():
                base_cell = b_info.get("base")
                if not base_cell: continue
                
                current_val = ws[base_cell].value
                expected_nombre = b_info.get("nombre")
                
                # Match 1: If cell already has this exact account name
                if current_val == account_name:
                    target_bank_info = b_info
                    break
                # Match 2: If JSON mapping expected this exact account name
                elif expected_nombre == account_name:
                    target_bank_info = b_info
                    break
                # Match 3: If cell is available (None, empty, or placeholder like 'BANCO 1')
                elif current_val is None or str(current_val).strip() == "" or str(current_val).upper().startswith("BANCO"):
                    if empty_bank_info is None:
                        empty_bank_info = b_info

            # If no direct match, use the first available block
            if not target_bank_info and empty_bank_info:
                target_bank_info = empty_bank_info

            if target_bank_info:
                # Always write the account name to the base cell so it's clearly identified
                ws[target_bank_info["base"]] = account_name

            if target_bank_info:
                # Update deposits for the specific month
                if month and deposits is not None:
                    dep_cell = target_bank_info.get("depositos", {}).get(month)
                    if dep_cell:
                        ws[dep_cell] = deposits
                
                # Update average balance for the specific month
                if month and avg_balance is not None:
                    bal_cell = target_bank_info.get("saldo_promedio", {}).get(month)
                    if bal_cell:
                        ws[bal_cell] = avg_balance

    # Fallback for simple key-value mappings
    elif mapping:
        # Just use the first document for simple mappings
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
