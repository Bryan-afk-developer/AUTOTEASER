import os

files = [
    'app/CAF/excel_builder.py',
    'app/CAF/Dictaminados/excel_builder_dictaminado.py'
]

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()

    # Remove the header definition for column E
    text = text.replace('            "E": ("Input / Ajuste", 18),\n', '')

    # Remove the styling code for column E in excel_builder.py
    text = text.replace("""                            # Col E: Input / Ajuste
                            e = ws[f"E{data_row}"]
                            e.fill = INPUT_FILL
                            e.alignment = Alignment(horizontal="right", vertical="center")
                            e.number_format = '#,##0.00'
                            e.border = THIN\n""", "")

    # Remove the styling code for column E in excel_builder_dictaminado.py (block 1)
    text = text.replace("""    e = ws[f"E{row_num}"]
    e.fill = INPUT_FILL
    e.alignment = Alignment(horizontal="right", vertical="center")
    e.number_format = '#,##0.00'
    e.border = THIN\n""", "")

    with open(file, 'w', encoding='utf-8') as f:
        f.write(text)

print("Column E removed successfully")
