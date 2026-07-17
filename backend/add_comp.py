import os

with open('app/CAF/excel_builder.py', 'r', encoding='utf-8') as f:
    text = f.read()

TARGET = """        # Fila 6: Indicador visual de si cuadra o no
        ws["J6"].value = "Resultado:"
        ws["J6"].font = Font(bold=True, size=10)
        ws["J6"].alignment = Alignment(horizontal="left", vertical="center")
        ws["J6"].border = THIN
        ws["K6"].value = '=IF(ABS(K5)<0.01,"SI CUADRA","NO CUADRA")'
        ws["K6"].font = Font(bold=True, size=11)
        ws["K6"].alignment = Alignment(horizontal="center", vertical="center")
        ws["K6"].border = THIN"""

REPLACEMENT = TARGET + """

        # ──────────────────────────────────────────────────────────
        # COLUMNA J-K: COMPROBACIÓN EDO RESULTADOS VS BALANCE
        # ──────────────────────────────────────────────────────────
        # J8: Header "COMPROBACIÓN RESULTADOS"
        j8 = ws["J8"]
        j8.value = "COMPROBACION RESULTADOS"
        j8.font = COMPROBACION_FONT
        j8.fill = COMPROBACION_FILL
        j8.alignment = Alignment(horizontal="center", vertical="center")
        j8.border = THIN
        k8 = ws["K8"]
        k8.fill = COMPROBACION_FILL
        k8.border = THIN
        ws.merge_cells("J8:K8")

        # Determine the template column for this year to compare
        tpl_col = "B"
        if "Balance" in mapa and year in mapa["Balance"]:
            tpl_col = mapa["Balance"][year].get("utilidad_ejercicio", "B78")[0]

        ver_res_rows = [
            ("Utilidad (Balance)", f"='Balance'!{tpl_col}78"),
            ("Utilidad (Edo Res)", f"='Edo de resultados'!{tpl_col}25"),
            ("Diferencia", "=K10-K9")
        ]

        for i, (label, formula) in enumerate(ver_res_rows, start=9):
            j = ws[f"J{i}"]
            j.value = label
            j.font = Font(bold=True, size=10)
            j.alignment = Alignment(horizontal="left", vertical="center")
            j.border = THIN
            j.fill = RESULT_FILL

            k = ws[f"K{i}"]
            k.value = formula
            k.font = RESULT_FONT
            k.number_format = '#,##0.00'
            k.alignment = Alignment(horizontal="right", vertical="center")
            k.border = THIN
            k.fill = RESULT_FILL

        ws["J12"].value = "Resultado:"
        ws["J12"].font = Font(bold=True, size=10)
        ws["J12"].alignment = Alignment(horizontal="left", vertical="center")
        ws["J12"].border = THIN
        ws["K12"].value = '=IF(ABS(K11)<0.01,"SI CUADRA","NO CUADRA")'
        ws["K12"].font = Font(bold=True, size=11)
        ws["K12"].alignment = Alignment(horizontal="center", vertical="center")
        ws["K12"].border = THIN"""

if TARGET in text:
    text = text.replace(TARGET, REPLACEMENT)
    with open('app/CAF/excel_builder.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Injected successfully")
else:
    print("Could not find target block")
