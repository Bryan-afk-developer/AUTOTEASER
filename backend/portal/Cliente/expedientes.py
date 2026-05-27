"""
expedientes.py — Consulta del expediente del cliente.

Calcula dinámicamente qué documentos se requieren y devuelve su estado actual.
Categorías:
  - Legal (Actas constitutiva y asambleas)
  - Estados de Cuenta (últimos 7 meses, desde 2 meses antes del actual)
  - Financieros (Balance, Resultados, Analíticas, Firmado × 4 periodos)
  - Declaraciones SAT (Acuse + Excel × 3 años fiscales cerrados)
  - Vigentes (Buró, CSF, Comprobante, Opinión, Currículum)
  - Representante Legal (INE, CSF, Acta Matrimonio, Comprobante Domicilio)

Endpoint:
- GET /api/portal/cliente/expediente
"""
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException, Header

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN ESTÁTICA DE DOCUMENTOS
# ══════════════════════════════════════════════════════════════════════════════

# 1. Documentos Legales
DOCUMENTOS_LEGALES = [
    {
        "clave": "acta_constitutiva",
        "nombre": "Acta Constitutiva y Asambleas Posteriores",
        "descripcion": "Acta constitutiva y asambleas posteriores con inscripción en el Registro Público de Comercio (RPC)",
        "categoria": "legal",
        "icono": "📜",
        "grupo": "legal",
    },
]

# 5. Documentos Vigentes (validez temporal)
DOCUMENTOS_VIGENTES = [
    {
        "clave": "buro_credito",
        "nombre": "Buró de Crédito",
        "descripcion": "Reporte de Buró de Crédito actualizado (vigente al mes actual)",
        "categoria": "fiscal",
        "icono": "📊",
        "grupo": "vigentes",
    },
    {
        "clave": "csf_empresa",
        "nombre": "Constancia de Situación Fiscal",
        "descripcion": "Emitida por el SAT, correspondiente al mes actual",
        "categoria": "fiscal",
        "icono": "🏛️",
        "grupo": "vigentes",
    },
    {
        "clave": "comprobante_domicilio_empresa",
        "nombre": "Comprobante de Domicilio",
        "descripcion": "No mayor a 3 meses, de preferencia recibo de luz",
        "categoria": "legal",
        "icono": "🏠",
        "grupo": "vigentes",
    },
    {
        "clave": "opinion_cumplimiento",
        "nombre": "Opinión de Cumplimiento",
        "descripcion": "Emitida por el SAT, correspondiente al mes actual",
        "categoria": "fiscal",
        "icono": "✅",
        "grupo": "vigentes",
    },
    {
        "clave": "curriculum_empresa",
        "nombre": "Currículum de la Empresa",
        "descripcion": "Presentación de la empresa o grupo empresarial",
        "categoria": "corporativo",
        "icono": "📋",
        "grupo": "vigentes",
    },
]

# 6. Documentos del Representante Legal
DOCUMENTOS_REPRESENTANTE = [
    {
        "clave": "ine_representante",
        "nombre": "INE o Identificación (Representante)",
        "descripcion": "Identificación oficial vigente (ambos lados)",
        "categoria": "legal",
        "icono": "🪪",
        "grupo": "representante",
    },
    {
        "clave": "csf_representante",
        "nombre": "Constancia de Situación Fiscal (Representante)",
        "descripcion": "Emitida por el SAT, vigente",
        "categoria": "fiscal",
        "icono": "🏛️",
        "grupo": "representante",
    },
    {
        "clave": "acta_matrimonio",
        "nombre": "Acta de Matrimonio",
        "descripcion": "En caso de aplicar",
        "categoria": "legal",
        "icono": "💍",
        "grupo": "representante",
    },
    {
        "clave": "comprobante_domicilio_representante",
        "nombre": "Comprobante de Domicilio (Representante)",
        "descripcion": "No mayor a 3 meses, de preferencia recibo de luz",
        "categoria": "legal",
        "icono": "🏠",
        "grupo": "representante",
    },
]

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ══════════════════════════════════════════════════════════════════════════════
# GENERADORES DINÁMICOS
# ══════════════════════════════════════════════════════════════════════════════

def calcular_estados_de_cuenta() -> list[dict]:
    """
    Genera los slots de estados de cuenta para los últimos 7 meses
    empezando 2 meses antes del mes actual.
    Ej: si estamos en Mayo 2026, empieza desde Marzo 2026 hacia atrás.
    """
    hoy = date.today()
    inicio = hoy - relativedelta(months=2)
    docs = []
    for i in range(7):
        fecha = inicio - relativedelta(months=i)
        mes_nombre = MESES_ES[fecha.month]
        año = fecha.year
        clave = f"estado_cuenta_{fecha.strftime('%Y_%m')}"
        docs.append({
            "clave": clave,
            "nombre": f"Estado de Cuenta – {mes_nombre} {año}",
            "descripcion": f"Estado de cuenta bancario del mes de {mes_nombre} {año}",
            "categoria": "bancario",
            "icono": "🏦",
            "mes": fecha.month,
            "año": año,
            "grupo": "estados_cuenta",
        })
    return docs


def calcular_financieros() -> list[dict]:
    """
    Genera los documentos de estados financieros requeridos.

    Los estados financieros se entregan como UN SOLO ARCHIVO por periodo
    que incluye: Balance General, Estado de Resultados, Analíticas y Firmado.

    Periodos:
      - Parcial al mes de 2 meses antes del actual (año en curso)
      - 3 años fiscales completos anteriores

    Ej: Mayo 2026 → Parcial Marzo 2026 + 2025 + 2024 + 2023
    """
    hoy = date.today()
    mes_parcial = hoy - relativedelta(months=2)
    año_actual = hoy.year

    # Periodo parcial del año en curso
    periodos = [
        {
            "sufijo": mes_parcial.strftime("%Y_%m"),
            "label": f"Parcial {MESES_ES[mes_parcial.month]} {mes_parcial.year}",
            "desc": f"Parciales al mes de {MESES_ES[mes_parcial.month]} {mes_parcial.year}",
        },
    ]
    # 3 años fiscales completos anteriores
    for i in range(1, 4):
        año = año_actual - i
        periodos.append({
            "sufijo": str(año),
            "label": f"Ejercicio Fiscal {año}",
            "desc": f"Ejercicio fiscal completo {año}",
        })

    docs = []
    for periodo in periodos:
        clave = f"financiero_eeff_{periodo['sufijo']}"
        docs.append({
            "clave": clave,
            "nombre": f"Estados Financieros – {periodo['label']}",
            "descripcion": (
                f"Un solo archivo que incluya: Balance General, Estado de Resultados, "
                f"Analíticas y Firmado · {periodo['desc']}"
            ),
            "categoria": "financiero",
            "icono": "📊",
            "grupo": "financieros",
        })

    return docs


def calcular_declaraciones() -> list[dict]:
    """
    Genera los documentos de declaraciones fiscales anuales.
    
    Regla: las declaraciones anuales salen el 31 de marzo.
      - Si ya pasó marzo → incluye el año inmediato anterior
      - Si no ha pasado marzo → empieza desde 2 años atrás
      - Siempre 3 años fiscales
    
    Cada año requiere 2 documentos:
      - Declaración Anual con Acuse (PDF)
      - Declaración Anual Excel SAT
    
    Ej: Mayo 2026 (pasó marzo) → 2025, 2024, 2023
    Ej: Feb 2026 (no ha pasado marzo) → 2024, 2023, 2022
    """
    hoy = date.today()

    if hoy.month >= 4:
        año_mas_reciente = hoy.year - 1
    else:
        año_mas_reciente = hoy.year - 2

    tipos = [
        ("acuse", "Declaración Anual con Acuse", "📋",
         "Declaración anual con acuse de recibo del SAT"),
        ("excel", "Declaración Anual – Excel SAT", "📊",
         "Archivo Excel descargado directamente del portal del SAT"),
    ]

    docs = []
    for i in range(3):
        año = año_mas_reciente - i
        for tipo_clave, tipo_nombre, tipo_icono, tipo_desc in tipos:
            clave = f"declaracion_{tipo_clave}_{año}"
            docs.append({
                "clave": clave,
                "nombre": f"{tipo_nombre} – {año}",
                "descripcion": f"{tipo_desc} · Ejercicio fiscal {año}",
                "categoria": "fiscal",
                "icono": tipo_icono,
                "grupo": "declaraciones",
                "año": año,
                "tipo_declaracion": tipo_clave,
            })

    return docs


# ══════════════════════════════════════════════════════════════════════════════
# COMBINADOR
# ══════════════════════════════════════════════════════════════════════════════

def get_todos_los_documentos_requeridos() -> list[dict]:
    """Combina todos los grupos de documentos en el orden de presentación."""
    return (
        DOCUMENTOS_LEGALES
        + calcular_estados_de_cuenta()
        + calcular_financieros()
        + calcular_declaraciones()
        + DOCUMENTOS_VIGENTES
        + DOCUMENTOS_REPRESENTANTE
    )


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/expediente")
async def get_expediente(authorization: str = Header(None)):
    """
    Devuelve el expediente completo del cliente:
    - Lista de todos los documentos requeridos
    - Estado actual de cada documento (FALTANTE, PENDIENTE, APROBADO, RECHAZADO)
    - Progreso general (% completado)
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    # Obtener empresa del usuario
    empresa_resp = (
        sb.table("empresas")
        .select("id, nombre")
        .eq("user_id", user_info["user_id"])
        .single()
        .execute()
    )
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa = empresa_resp.data
    empresa_id = empresa["id"]

    # Obtener documentos ya subidos de la BD (de ambas tablas)
    docs_resp = (
        sb.table("documentos_expediente")
        .select("*")
        .eq("empresa_id", empresa_id)
        .execute()
    )
    docs_empresa = docs_resp.data or []

    # Obtener documentos del representante
    rep_resp = (
        sb.table("documentos_representante")
        .select("*")
        .eq("empresa_id", empresa_id)
        .execute()
    )
    docs_representante = rep_resp.data or []

    # Combinar todos los documentos subidos
    todos_subidos = docs_empresa + docs_representante
    docs_subidos = {d["tipo_documento"]: d for d in todos_subidos}

    # Construir respuesta combinando requeridos con los subidos
    documentos_requeridos = get_todos_los_documentos_requeridos()
    resultado = []
    aprobados = 0

    for doc_req in documentos_requeridos:
        clave = doc_req["clave"]
        doc_subido = docs_subidos.get(clave)

        if doc_subido:
            estado = doc_subido["estado"]
            entry = {
                **doc_req,
                "estado": estado,
                "documento_id": doc_subido["id"],
                "nombre_archivo": doc_subido.get("nombre_archivo"),
                "subido_en": doc_subido.get("subido_en"),
                "revisado_en": doc_subido.get("revisado_en"),
                "comentario_admin": doc_subido.get("comentario_admin"),
                "storage_path": doc_subido.get("storage_path"),
            }
            if estado == "APROBADO":
                aprobados += 1
        else:
            entry = {
                **doc_req,
                "estado": "FALTANTE",
                "documento_id": None,
                "nombre_archivo": None,
                "subido_en": None,
                "revisado_en": None,
                "comentario_admin": None,
                "storage_path": None,
            }

        resultado.append(entry)

    total = len(resultado)
    progreso = round((aprobados / total) * 100) if total > 0 else 0

    return {
        "empresa_id": empresa_id,
        "nombre_empresa": empresa["nombre"],
        "documentos": resultado,
        "resumen": {
            "total": total,
            "aprobados": aprobados,
            "pendientes": sum(1 for d in resultado if d["estado"] == "PENDIENTE"),
            "rechazados": sum(1 for d in resultado if d["estado"] == "RECHAZADO"),
            "faltantes": sum(1 for d in resultado if d["estado"] == "FALTANTE"),
            "progreso_porcentaje": progreso,
        },
    }
