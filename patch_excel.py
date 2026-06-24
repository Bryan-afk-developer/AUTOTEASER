import os
import re

file_path = "backend/app/CAF/excel_builder.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add _extract_pairs_dictaminado
dictaminado_func = """
def _extract_pairs_dictaminado(row):
    tokens = _tokenize_cells(row)
    if not tokens: return []
    pairs = []
    current_concept = []
    amounts = []
    for t in tokens:
        if t in _OCR_NOISE: continue
        if _is_numeric(t) or t == "-":
            amounts.append(t)
        else:
            if amounts:
                c = " ".join(current_concept).strip()
                m1 = amounts[0] if len(amounts) > 0 else ""
                m2 = amounts[1] if len(amounts) > 1 else ""
                pairs.append((c, m1, m2))
                current_concept = [t]
                amounts = []
            else:
                current_concept.append(t)
    if current_concept or amounts:
        c = " ".join(current_concept).strip()
        m1 = amounts[0] if len(amounts) > 0 else ""
        m2 = amounts[1] if len(amounts) > 1 else ""
        pairs.append((c, m1, m2))
    return pairs

def _extract_pairs_two_column
"""
content = content.replace("def _extract_pairs_two_column", dictaminado_func.strip("\n"), 1)

# 2. Add is_dictaminado handling in the inner loop
split_logic = """                        elif layout_type == "split_column":
                            concept_text = ""
                            amount_text = ""
                            for cell in row:
                                if cell.get("is_concept"): concept_text = cell.get("text", "")
                                elif cell.get("is_amount"): amount_text = cell.get("text", "")
                            page_single_pairs.append((concept_text, amount_text, evidence_b64))"""

dictaminado_logic = split_logic + """
                        elif is_dictaminado:
                            d_pairs = _extract_pairs_dictaminado(row)
                            for c, m1, m2 in d_pairs:
                                m = m1 if year_idx == 0 else m2
                                page_single_pairs.append((c, m, evidence_b64))"""

content = content.replace(split_logic, dictaminado_logic, 1)

# 3. Replace the year parsing and indent the loop
old_year_parsing = """    for doc in docs_data:
        # ── Detectar año ─────────────────────────────────────────
        year = str(doc.get("year", "")).strip()
        if not year or year == "Desconocido":
            m = re.search(r'\\b(20[1-2]\\d)\\b', doc.get("filename", ""))
            year = m.group(1) if m else None
        if not year:
            import uuid
            year = f"Desc_{uuid.uuid4().hex[:4]}"

        sheet_name = year"""

new_year_parsing = """    for doc in docs_data:
        doc_type = doc.get("doc_type", "financiero")
        if "extracted_data" in doc and "doc_type" in doc["extracted_data"]:
            doc_type = doc["extracted_data"]["doc_type"]
            
        is_dictaminado = (doc_type == "dictaminado")
        year_str = str(doc.get("year", "")).strip()
        
        if is_dictaminado and "," in year_str:
            years = [y.strip() for y in year_str.split(",") if y.strip()]
        else:
            years = [year_str]
            
        if not years or not any(years) or years[0] == "Desconocido":
            m = re.search(r'\\b(20[1-2]\\d)\\b', doc.get("filename", ""))
            if m:
                years = [m.group(1)]
            else:
                import uuid
                years = [f"Desc_{uuid.uuid4().hex[:4]}"]

        for year_idx, current_year in enumerate(years):
            sheet_name = current_year"""

content = content.replace(old_year_parsing, new_year_parsing, 1)

# Now we need to indent everything from `orig = sheet_name` down to `col_f.border = THIN`
lines = content.split('\n')
in_indent_block = False
new_lines = []

for line in lines:
    if line.startswith("        orig = sheet_name"):
        in_indent_block = True
    elif line.startswith("    if \"Plantilla_Vaciado\" in wb.sheetnames:"):
        in_indent_block = False
        
    if in_indent_block and line.startswith("        "):
        new_lines.append("    " + line)
    elif in_indent_block and not line.strip():
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines))

print("Patched excel_builder.py!")
