"""
accionistas.py — CRUD de Accionistas por empresa.

Endpoints:
- POST /api/portal/cliente/accionistas           → Crear nuevo accionista (sin nombre obligatorio)
- GET  /api/portal/cliente/accionistas           → Listar accionistas de la empresa
- PUT  /api/portal/cliente/accionistas/{id}      → Actualizar nombre
- DELETE /api/portal/cliente/accionistas/{id}   → Eliminar accionista
"""
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()

# Documentos que se piden a cada accionista (mismo que representante)
DOCUMENTOS_ACCIONISTA = [
    {"clave": "ine_accionista",   "nombre": "INE o Identificación", "icono": "🪪"},
    {"clave": "csf_accionista",   "nombre": "Constancia de Situación Fiscal", "icono": "🏛️"},
    {"clave": "comprobante_domicilio_accionista", "nombre": "Comprobante de Domicilio", "icono": "🏠"},
    {"clave": "buro_accionista",  "nombre": "Buró de Crédito", "icono": "📊"},
    {"clave": "acta_matrimonio_accionista", "nombre": "Acta de Matrimonio", "icono": "💍"},
    {"clave": "buro_score_accionista", "nombre": "Buró de Crédito Score", "icono": "📈"},
]


class AccionistaCreate(BaseModel):
    nombre: Optional[str] = None   # No es obligatorio


class AccionistaUpdate(BaseModel):
    nombre: str


@router.post("/accionistas")
async def crear_accionista(
    payload: AccionistaCreate,
    authorization: str = Header(None),
):
    """Crea un nuevo slot de accionista para la empresa del usuario."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    # Obtener el siguiente número de orden
    existing = sb.table("accionistas").select("orden").eq("empresa_id", empresa_id).execute()
    max_orden = max((r["orden"] for r in (existing.data or [])), default=0)
    nuevo_orden = max_orden + 1

    data = {
        "empresa_id": empresa_id,
        "nombre": payload.nombre or f"Accionista {nuevo_orden}",
        "orden": nuevo_orden,
    }
    result = sb.table("accionistas").insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="No se pudo crear el accionista")

    accionista = result.data[0]
    # Devolver con los tipos de documentos disponibles
    accionista["documentos_requeridos"] = DOCUMENTOS_ACCIONISTA
    accionista["documentos"] = []
    return accionista


@router.get("/accionistas")
async def listar_accionistas(authorization: str = Header(None)):
    """Lista todos los accionistas de la empresa, con el estado de sus documentos."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    accionistas_resp = sb.table("accionistas").select("*").eq("empresa_id", empresa_id).order("orden").execute()
    accionistas = accionistas_resp.data or []

    # Enriquecer cada accionista con sus documentos subidos
    for acc in accionistas:
        docs_resp = sb.table("documentos_accionista").select("*").eq("accionista_id", acc["id"]).execute()
        docs_subidos = {d["tipo_documento"]: d for d in (docs_resp.data or [])}

        slots = []
        for req in DOCUMENTOS_ACCIONISTA:
            clave = req["clave"]
            if clave in docs_subidos:
                d = docs_subidos[clave]
                slots.append({**req, "estado": d["estado"], "nombre_archivo": d["nombre_archivo"],
                               "documento_id": d["id"], "storage_path": d["storage_path"]})
            else:
                slots.append({**req, "estado": "pendiente", "nombre_archivo": None,
                               "documento_id": None, "storage_path": None})
        acc["documentos"] = slots
        acc["documentos_requeridos"] = DOCUMENTOS_ACCIONISTA

    return {"accionistas": accionistas}


@router.put("/accionistas/{accionista_id}")
async def actualizar_accionista(
    accionista_id: str,
    payload: AccionistaUpdate,
    authorization: str = Header(None),
):
    """Actualiza el nombre de un accionista."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    result = sb.table("accionistas").update({"nombre": payload.nombre})\
        .eq("id", accionista_id).eq("empresa_id", empresa_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Accionista no encontrado")
    return result.data[0]


@router.delete("/accionistas/{accionista_id}")
async def eliminar_accionista(
    accionista_id: str,
    authorization: str = Header(None),
):
    """Elimina un accionista y todos sus documentos (CASCADE en BD)."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    empresa_id = user_info["empresa_id"]

    sb.table("accionistas").delete().eq("id", accionista_id).eq("empresa_id", empresa_id).execute()
    return {"message": "Accionista eliminado"}
