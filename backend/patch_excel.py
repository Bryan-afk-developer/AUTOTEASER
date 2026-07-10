import os

parse_fn = """
def parse_amount(value: str):
    import re
    if not value:
        return value
    s = str(value).strip()
    
    negative = s.startswith('(') and s.endswith(')')
    if negative:
        s = s[1:-1]
        
    s = re.sub(r'[$€£\\s]', '', s)
    if not s:
        return value
        
    last_dot = s.rfind('.')
    last_comma = s.rfind(',')
    
    if last_dot > last_comma:
        s = s.replace(',', '')
    elif last_comma > last_dot:
        s = s.replace('.', '')
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '.')
        
    try:
        result = float(s)
        return -result if negative else result
    except ValueError:
        return value
"""

# Patch excel_builder.py
with open("app/CAF/excel_builder.py", "r", encoding="utf-8") as f:
    content = f.read()

if "def parse_amount" not in content:
    content = content.replace("logger = logging.getLogger(__name__)", "logger = logging.getLogger(__name__)\n" + parse_fn)
    
content = content.replace(
"""                            # Col B: Monto
                            b = ws[f"B{data_row}"]
                            b.value = monto
                            b.alignment = Alignment(vertical="center", horizontal="right")
                            b.border = THIN""",
"""                            # Col B: Monto
                            b = ws[f"B{data_row}"]
                            parsed_monto = parse_amount(monto)
                            b.value = parsed_monto
                            b.alignment = Alignment(vertical="center", horizontal="right")
                            b.border = THIN
                            if isinstance(parsed_monto, (int, float)):
                                b.number_format = '#,##0.00'""")
                                
with open("app/CAF/excel_builder.py", "w", encoding="utf-8") as f:
    f.write(content)
    
# Patch excel_builder_dictaminado.py
with open("app/CAF/Dictaminados/excel_builder_dictaminado.py", "r", encoding="utf-8") as f:
    content2 = f.read()
    
if "def parse_amount" not in content2:
    content2 = content2.replace("logger = logging.getLogger(__name__)", "logger = logging.getLogger(__name__)\n" + parse_fn)

content2 = content2.replace(
"""    b = ws[f"B{row_num}"]
    b.value = monto
    b.fill = fill
    b.alignment = Alignment(horizontal="right")
    b.border = THIN""",
"""    b = ws[f"B{row_num}"]
    parsed_monto = parse_amount(monto)
    b.value = parsed_monto
    b.fill = fill
    b.alignment = Alignment(horizontal="right")
    b.border = THIN
    if isinstance(parsed_monto, (int, float)):
        b.number_format = '#,##0.00'""")

with open("app/CAF/Dictaminados/excel_builder_dictaminado.py", "w", encoding="utf-8") as f:
    f.write(content2)

print("Patched successfully")
