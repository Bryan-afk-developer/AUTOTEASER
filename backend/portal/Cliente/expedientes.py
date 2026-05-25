"""
expedientes.py — Consulta del expediente del cliente.

Calcula dinámicamente qué documentos se requieren (últimos 6 meses de estados
de cuenta + documentos fijos de la empresa) y devuelve su estado actual.

Endpoint:
- GET /api/portal/cliente/expediente
"""
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException, Header

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Configuración de documentos requeridos ────────────────────────────────────

# Documentos de Empresa
DOCUMENTOS_EMPRESA = [
    {
        "clave": "acta_constitutiva",
        "nombre": "Acta Constitutiva",
        "descripcion": "Acta de constitución de la empresa con sello del Registro Público",
        "categoria": "legal",
        "icono": "📄",
        "grupo": "empresa"
    },
    {
        "clave": "csf_empresa",
        "nombre": "Constancia de Situación Fiscal (Empresa)",
        "descripcion": "Emitida por el SAT, vigente (no mayor a 3 meses)",
        "categoria": "fiscal",
        "icono": "🏛️",
        "grupo": "empresa"
    },
    {
        "clave": "comprobante_domicilio_empresa",
        "nombre": "Comprobante de Domicilio (Empresa)",
        "descripcion": "No mayor a 3 meses y de preferencia Luz",
        "categoria": "legal",
        "icono": "🏠",
        "grupo": "empresa"
    },
]

# Documentos del Representante Legal
DOCUMENTOS_REPRESENTANTE = [
    {
        "clave": "ine_representante",
        "nombre": "INE o Identificación (Representante)",
        "descripcion": "Identificación oficial vigente (ambos lados)",
        "categoria": "legal",
        "icono": "🪪",
        "grupo": "representante"
    },
    {
        "clave": "csf_representante",
        "nombre": "Constancia de Situación Fiscal (Representante)",
        "descripcion": "Emitida por el SAT, vigente",
        "categoria": "fiscal",
        "icono": "🏛️",
        "grupo": "representante"
    },
    {
        "clave": "acta_matrimonio",
        "nombre": "Acta de Matrimonio",
        "descripcion": "En caso de aplicar",
        "categoria": "legal",
        "icono": "💍",
        "grupo": "representante"
    },
    {
        "clave": "comprobante_domicilio_representante",
        "nombre": "Comprobante de Domicilio (Representante)",
        "descripcion": "No mayor a 3 meses y de preferencia Luz",
        "categoria": "legal",
        "icono": "🏠",
        "grupo": "representante"
    },
]

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def calcular_estados_de_cuenta() -> list[dict]:
    """
    Genera los slots de estados de cuenta para los últimos 7 meses
    excluyendo el mes actual.
    """
    hoy = date.today()
    inicio = hoy - relativedelta(months=1)
    docs = []
    for i in range(7):
        fecha = inicio - relativedelta(months=i)
        mes_nombre = MESES_ES[fecha.month]
        año = fecha.year
        clave = f"estado_cuenta_{fecha.strftime('%Y_%m')}"
        docs.append({
            "clave": clave,
            "nombre": f"Estado de Cuenta {mes_nombre} {año}",
            "descripcion": f"Estado de cuenta bancario del mes de {mes_nombre} {año}",
            "categoria": "bancario",
            "icono": "🏦",
            "mes": fecha.month,
            "año": año,
            "grupo": "estados_cuenta"
        })
    return docs


def get_todos_los_documentos_requeridos() -> list[dict]:
    """Combina documentos fijos + estados de cuenta dinámicos."""
    return DOCUMENTOS_EMPRESA + calcular_estados_de_cuenta() + DOCUMENTOS_REPRESENTANTE


# ── Endpoint ──────────────────────────────────────────────────────────────────

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
    empresa_resp = sb.table("empresas").select("id, nombre").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa = empresa_resp.data
    empresa_id = empresa["id"]

    # Obtener documentos ya subidos de la BD (de ambas tablas)
    docs_resp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).execute()
    docs_empresa = docs_resp.data or []

    # Obtener documentos del representante
    rep_resp = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).execute()
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
        }
    }
