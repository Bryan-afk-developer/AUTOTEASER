import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()

DOCUMENTOS_SUB_EMPRESA = [
    {"clave": "csf_sub_empresa", "nombre": "Constancia de Situación Fiscal", "icono": "🏛️"},
    {"clave": "comprobante_domicilio_sub_empresa", "nombre": "Comprobante de Domicilio", "icono": "🏠"},
    {"clave": "opinion_cumplimiento_sub_empresa", "nombre": "Opinión de Cumplimiento", "icono": "✅"},
    {"clave": "buro_sub_empresa", "nombre": "Buró de Crédito", "icono": "📊"},
    {"clave": "acta_constitutiva_sub_empresa", "nombre": "Acta Constitutiva", "icono": "📜"},
    {"clave": "estados_financieros_sub_empresa", "nombre": "Estados Financieros", "icono": "💰"},
    {"clave": "declaraciones_sub_empresa", "nombre": "Declaraciones", "icono": "📝"},
    {"clave": "estados_cuenta_sub_empresa", "nombre": "Estados de Cuenta", "icono": "🏦"},
    {"clave": "curriculum_sub_empresa", "nombre": "Currículum de la Empresa", "icono": "📋"},
]

class SubEmpresaCreate(BaseModel):
    nombre: Optional[str] = None
    rol: str

class SubEmpresaUpdate(BaseModel):
    nombre: str
    rol: str

@router.post("/sub-empresas")
async def crear_sub_empresa(payload: SubEmpresaCreate, authorization: str = Header(None)):
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    if payload.rol not in ["EMPRESA AVAL", "EMPRESA DEL GRUPO"]:
        raise HTTPException(status_code=400, detail="Rol inválido")

    existing = sb.table("sub_empresas").select("orden").eq("empresa_id", empresa_id).execute()
    max_orden = max((r["orden"] for r in (existing.data or [])), default=0)
    nuevo_orden = max_orden + 1

    data = {
        "empresa_id": empresa_id,
        "nombre": payload.nombre or f"Sub Empresa {nuevo_orden}",
        "rol": payload.rol,
        "orden": nuevo_orden,
    }
    result = sb.table("sub_empresas").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="No se pudo crear la sub empresa")

    sub_empresa = result.data[0]
    sub_empresa["documentos_requeridos"] = DOCUMENTOS_SUB_EMPRESA
    sub_empresa["documentos"] = []
    return sub_empresa

@router.get("/sub-empresas")
async def listar_sub_empresas(authorization: str = Header(None)):
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    sub_resp = sb.table("sub_empresas").select("*").eq("empresa_id", empresa_id).order("orden").execute()
    sub_empresas = sub_resp.data or []

    for sub in sub_empresas:
        docs_resp = sb.table("documentos_sub_empresa").select("*").eq("sub_empresa_id", sub["id"]).execute()
        docs_subidos = {d["tipo_documento"]: d for d in (docs_resp.data or [])}

        slots = []
        for req in DOCUMENTOS_SUB_EMPRESA:
            clave = req["clave"]
            if clave in docs_subidos:
                d = docs_subidos[clave]
                slots.append({**req, "estado": d["estado"], "nombre_archivo": d["nombre_archivo"],
                               "documento_id": d["id"], "storage_path": d["storage_path"]})
            else:
                slots.append({**req, "estado": "pendiente", "nombre_archivo": None,
                               "documento_id": None, "storage_path": None})
        sub["documentos"] = slots
        sub["documentos_requeridos"] = DOCUMENTOS_SUB_EMPRESA

    return {"sub_empresas": sub_empresas}

@router.put("/sub-empresas/{sub_empresa_id}")
async def actualizar_sub_empresa(sub_empresa_id: str, payload: SubEmpresaUpdate, authorization: str = Header(None)):
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    if payload.rol not in ["EMPRESA AVAL", "EMPRESA DEL GRUPO"]:
        raise HTTPException(status_code=400, detail="Rol inválido")

    result = sb.table("sub_empresas").update({"nombre": payload.nombre, "rol": payload.rol})\
        .eq("id", sub_empresa_id).eq("empresa_id", empresa_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Sub empresa no encontrada")
    return result.data[0]

@router.delete("/sub-empresas/{sub_empresa_id}")
async def eliminar_sub_empresa(sub_empresa_id: str, authorization: str = Header(None)):
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    sb.table("sub_empresas").delete().eq("id", sub_empresa_id).eq("empresa_id", empresa_id).execute()
    return {"message": "Sub empresa eliminada"}
