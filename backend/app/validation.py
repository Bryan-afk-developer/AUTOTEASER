"""
AutoCAF - Accounting Validation Module

Automatic validation of financial data:
- Balance: Activo = Pasivo + Capital
- Edo Resultados: Ventas - Costos - Gastos ≈ Utilidad Neta
- Cross-year: utilidad_ejercicio(Y) ≈ resultados_ejercicios_anteriores(Y+1)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# BALANCE GENERAL VALIDATION
# ══════════════════════════════════════════════════════════════════

def _sum_activo_circulante(b: dict) -> float:
    """Sum all current assets."""
    keys = [
        "caja", "bancos", "clientes", "cuentas_por_cobrar",
        "deudores_diversos", "isr_diferido", "impuestos_a_favor",
        "inventarios", "pagos_anticipados", "anticipo_proveedores",
    ]
    return sum(abs(b.get(k, 0)) for k in keys)


def _sum_activo_fijo(b: dict) -> float:
    """Sum all fixed assets (net of depreciation)."""
    keys = [
        "edificios", "maquinaria_equipo", "equipo_transporte",
        "mobiliario_equipo", "equipo_computo", "otros_activos_fijos",
        "terrenos",
    ]
    total = sum(abs(b.get(k, 0)) for k in keys)
    total -= abs(b.get("depreciacion_acumulada", 0))
    return total


def _sum_activo_diferido(b: dict) -> float:
    """Sum all deferred assets."""
    keys = [
        "gastos_instalacion", "depositos_garantia",
        "otros_activos_largo_plazo",
    ]
    return sum(abs(b.get(k, 0)) for k in keys)


def _sum_pasivo_cp(b: dict) -> float:
    """Sum all current liabilities."""
    keys = [
        "proveedores", "prestamos_bancarios_cp", "acreedores_diversos",
        "otros_pasivos_cp", "impuestos_acumulados", "anticipo_clientes",
    ]
    return sum(abs(b.get(k, 0)) for k in keys)


def _sum_pasivo_lp(b: dict) -> float:
    """Sum all long-term liabilities."""
    keys = ["prestamos_bancarios_lp", "otras_cuentas_lp"]
    return sum(abs(b.get(k, 0)) for k in keys)


def _sum_capital(b: dict) -> float:
    """Sum all equity components."""
    capital = abs(b.get("capital_social", 0))
    capital += abs(b.get("reserva_legal", 0))
    capital += abs(b.get("aportaciones_futuros_aumentos", 0))
    # These can be negative (accumulated losses)
    capital += b.get("resultados_ejercicios_anteriores", 0)
    capital += b.get("utilidad_ejercicio", 0)
    return capital


def validate_balance(balance_data: dict, tolerance_pct: float = 0.02) -> dict:
    """
    Validate the fundamental accounting equation: Activo = Pasivo + Capital.

    Args:
        balance_data: dict of {field: value} for a single year
        tolerance_pct: acceptable difference as fraction (default 2%)

    Returns:
        dict with validation results
    """
    ac = _sum_activo_circulante(balance_data)
    af = _sum_activo_fijo(balance_data)
    ad = _sum_activo_diferido(balance_data)
    total_activo = ac + af + ad

    pcp = _sum_pasivo_cp(balance_data)
    plp = _sum_pasivo_lp(balance_data)
    total_pasivo = pcp + plp

    total_capital = _sum_capital(balance_data)

    pasivo_mas_capital = total_pasivo + total_capital
    diff = abs(total_activo - pasivo_mas_capital)
    denom = max(total_activo, 1)
    diff_pct = diff / denom

    is_valid = diff_pct <= tolerance_pct

    result = {
        "valid": is_valid,
        "activo_circulante": round(ac, 2),
        "activo_fijo_neto": round(af, 2),
        "activo_diferido": round(ad, 2),
        "total_activo": round(total_activo, 2),
        "pasivo_cp": round(pcp, 2),
        "pasivo_lp": round(plp, 2),
        "total_pasivo": round(total_pasivo, 2),
        "total_capital": round(total_capital, 2),
        "pasivo_mas_capital": round(pasivo_mas_capital, 2),
        "diferencia": round(diff, 2),
        "diferencia_pct": round(diff_pct * 100, 2),
        "ecuacion": f"Activo ({total_activo:,.2f}) {'=' if is_valid else '≠'} "
                    f"Pasivo ({total_pasivo:,.2f}) + Capital ({total_capital:,.2f})",
    }

    if is_valid:
        logger.info(f"✅ Balance OK: {result['ecuacion']}")
    else:
        logger.warning(f"❌ Balance FAIL: {result['ecuacion']} | Δ={diff:,.2f} ({diff_pct:.1%})")

    return result


# ══════════════════════════════════════════════════════════════════
# ESTADO DE RESULTADOS VALIDATION
# ══════════════════════════════════════════════════════════════════

def validate_edo_resultados(edo_data: dict, balance_data: Optional[dict] = None,
                            tolerance_pct: float = 0.05) -> dict:
    """
    Validate Estado de Resultados internal consistency.

    Checks:
    - Utilidad Bruta = Ventas - Costo de Ventas
    - Utilidad Operativa = U. Bruta - Gastos Generales
    - Utilidad Neta ≈ utilidad_ejercicio from Balance (cross-check)
    """
    ventas = abs(edo_data.get("ventas", 0))
    costo = abs(edo_data.get("costo_ventas", 0))
    gastos = abs(edo_data.get("gastos_generales", 0))
    gastos_admin = abs(edo_data.get("gastos_administracion", 0))
    gastos_fin = abs(edo_data.get("gastos_financieros", 0))
    prod_fin = abs(edo_data.get("productos_financieros", 0))
    otros_gastos = abs(edo_data.get("otros_gastos", 0))
    otros_ingresos = abs(edo_data.get("otros_ingresos", 0))
    impuestos = abs(edo_data.get("impuestos", 0))

    utilidad_bruta = ventas - costo
    utilidad_operativa = utilidad_bruta - gastos

    # Approximate net income
    utilidad_neta_calc = (
        utilidad_operativa
        - gastos_fin + prod_fin
        - otros_gastos + otros_ingresos
        - impuestos
    )

    checks = []

    # Check: Utilidad Bruta makes sense
    if ventas > 0:
        margen_bruto = utilidad_bruta / ventas
        checks.append({
            "check": "Margen Bruto",
            "value": f"{margen_bruto:.1%}",
            "valid": -0.5 <= margen_bruto <= 1.0,
            "detail": f"Ventas ({ventas:,.2f}) - Costo ({costo:,.2f}) = {utilidad_bruta:,.2f}",
        })

    # Cross-check with Balance's utilidad_ejercicio
    if balance_data:
        bal_utilidad = balance_data.get("utilidad_ejercicio", 0)
        if bal_utilidad != 0:
            diff = abs(utilidad_neta_calc - bal_utilidad)
            denom = max(abs(bal_utilidad), 1)
            checks.append({
                "check": "Utilidad Neta vs Balance",
                "value": f"Δ {diff:,.2f}",
                "valid": (diff / denom) <= tolerance_pct,
                "detail": f"Edo: {utilidad_neta_calc:,.2f} vs Balance: {bal_utilidad:,.2f}",
            })

    all_valid = all(c["valid"] for c in checks) if checks else True

    return {
        "valid": all_valid,
        "ventas": round(ventas, 2),
        "costo_ventas": round(costo, 2),
        "utilidad_bruta": round(utilidad_bruta, 2),
        "gastos_generales": round(gastos, 2),
        "utilidad_operativa": round(utilidad_operativa, 2),
        "utilidad_neta_calculada": round(utilidad_neta_calc, 2),
        "checks": checks,
    }


# ══════════════════════════════════════════════════════════════════
# CROSS-YEAR VALIDATION
# ══════════════════════════════════════════════════════════════════

def cross_validate_years(multi_year_data: dict, tolerance_pct: float = 0.05) -> list:
    """
    Cross-validate consecutive years.

    Check: utilidad_ejercicio(year N) should appear as part of
    resultados_ejercicios_anteriores(year N+1).

    Args:
        multi_year_data: dict of {year_str: {field: value}} for Balance
    """
    years = sorted(multi_year_data.keys())
    results = []

    for i in range(len(years) - 1):
        y_current = years[i]
        y_next = years[i + 1]

        utilidad_current = multi_year_data[y_current].get("utilidad_ejercicio", 0)
        res_ant_next = multi_year_data[y_next].get("resultados_ejercicios_anteriores", 0)
        res_ant_current = multi_year_data[y_current].get("resultados_ejercicios_anteriores", 0)

        # The next year's accumulated results should be approximately
        # current year's accumulated + current year's net income
        expected = res_ant_current + utilidad_current
        diff = abs(expected - res_ant_next)
        denom = max(abs(expected), abs(res_ant_next), 1)

        is_close = (diff / denom) <= tolerance_pct

        results.append({
            "years": f"{y_current} → {y_next}",
            "valid": is_close,
            "utilidad_ejercicio": round(utilidad_current, 2),
            "res_ant_esperado": round(expected, 2),
            "res_ant_real": round(res_ant_next, 2),
            "diferencia": round(diff, 2),
        })

    return results


# ══════════════════════════════════════════════════════════════════
# FULL VALIDATION REPORT
# ══════════════════════════════════════════════════════════════════

def generate_validation_report(processed_docs: list[dict]) -> dict:
    """
    Generate a complete validation report for multiple processed documents.

    Args:
        processed_docs: list of dicts, each with:
            - llm_result.data.Balance.{year: {fields}}
            - llm_result.data.Edo de resultados.{year: {fields}}

    Returns:
        Comprehensive validation report
    """
    balance_validations = {}
    edo_validations = {}
    all_balance_years = {}

    for doc in processed_docs:
        llm = doc.get("llm_result") or {}
        data = llm.get("data") or {}

        balance = data.get("Balance", {})
        edo = data.get("Edo de resultados", {})

        for year, fields in balance.items():
            if not isinstance(fields, dict):
                continue
            balance_validations[year] = validate_balance(fields)
            all_balance_years[year] = fields

            edo_fields = edo.get(year, {})
            if isinstance(edo_fields, dict) and edo_fields:
                edo_validations[year] = validate_edo_resultados(edo_fields, fields)

    # Cross-year validation
    cross_year = []
    if len(all_balance_years) > 1:
        cross_year = cross_validate_years(all_balance_years)

    # Overall status
    all_balance_ok = all(v["valid"] for v in balance_validations.values())
    all_edo_ok = all(v["valid"] for v in edo_validations.values())

    return {
        "overall_valid": all_balance_ok and all_edo_ok,
        "balance": balance_validations,
        "edo_resultados": edo_validations,
        "cross_year": cross_year,
        "years_processed": sorted(all_balance_years.keys()),
        "summary": {
            "total_years": len(all_balance_years),
            "balance_ok": sum(1 for v in balance_validations.values() if v["valid"]),
            "balance_fail": sum(1 for v in balance_validations.values() if not v["valid"]),
            "edo_ok": sum(1 for v in edo_validations.values() if v["valid"]),
            "edo_fail": sum(1 for v in edo_validations.values() if not v["valid"]),
        },
    }
