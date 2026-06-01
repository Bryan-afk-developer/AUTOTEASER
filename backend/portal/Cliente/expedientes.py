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

def calcular_estados_de_cuenta(banco: dict = None) -> list[dict]:
    """
    Genera 7 slots genéricos para estados de cuenta de la cuenta bancaria.
    """
    docs = []
    
    # Si no hay banco, no devolvemos slots genéricos
    if not banco:
        return docs
        
    nombre_banco = banco["nombre_banco"]
    cuenta_id = banco["id"]
    
    for i in range(1, 8):
        clave = f"ec_{cuenta_id}_{i}"
        docs.append({
            "clave": clave,
            "nombre": f"Estado de Cuenta {i}",
            "descripcion": f"Documento de estado de cuenta #{i}",
            "categoria": "bancario",
            "icono": "🏦",
            "grupo": "estados_cuenta",
            "cuenta_bancaria_id": cuenta_id,
            "nombre_carpeta": nombre_banco,
            "orden": i
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

def get_todos_los_documentos_requeridos(bancos: list[dict] = None) -> list[dict]:
    """Combina todos los grupos de documentos en el orden de presentación."""
    docs_bancos = []
    if bancos:
        for banco in bancos:
            docs_bancos.extend(calcular_estados_de_cuenta(banco))

    return (
        DOCUMENTOS_LEGALES
        + docs_bancos
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
    Devuelve el expediente completo del cliente.
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

    # Obtener bancos
    bancos_resp = sb.table("cuentas_bancarias").select("*").eq("empresa_id", empresa_id).execute()
    bancos = bancos_resp.data or []

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
    documentos_requeridos = get_todos_los_documentos_requeridos(bancos)
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
        "bancos": bancos,
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

@router.post("/carpetas-banco")
async def crear_carpeta_banco(
    nombre_banco: str,
    authorization: str = Header(None)
):
    """Crea una nueva carpeta de banco para la empresa."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    try:
        result = sb.table("cuentas_bancarias").insert({
            "empresa_id": empresa_id,
            "nombre_banco": nombre_banco
        }).execute()
        return result.data[0]
    except Exception as e:
        logger.error(f"Error creando cuenta bancaria: {e}")
        raise HTTPException(status_code=400, detail="La cuenta bancaria ya existe o hubo un error")

@router.delete("/carpetas-banco/{cuenta_id}")
async def eliminar_carpeta_banco(
    cuenta_id: str,
    authorization: str = Header(None)
):
    """Elimina una cuenta bancaria y sus documentos si no están aprobados."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    # Verificar si hay documentos aprobados
    docs_resp = sb.table("documentos_expediente").select("estado").eq("cuenta_bancaria_id", cuenta_id).execute()
    if docs_resp.data:
        if any(d["estado"] == "APROBADO" for d in docs_resp.data):
            raise HTTPException(status_code=400, detail="No puedes eliminar un banco con documentos aprobados")

    sb.table("cuentas_bancarias").delete().eq("id", cuenta_id).eq("empresa_id", empresa_id).execute()
    return {"message": "Cuenta bancaria eliminada"}
