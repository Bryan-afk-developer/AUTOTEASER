"""
revision.py — Revisión de documentos por el equipo Admin.

Endpoint:
- PATCH /api/portal/admin/documentos/{doc_id}/revisar
  Cambia el estado de un documento a APROBADO o RECHAZADO y guarda el comentario.
- GET  /api/portal/admin/documentos/{doc_id}
  Devuelve el detalle de un documento + URL firmada para visualizarlo.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from portal.shared.supabase_db import get_supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()

BUCKET_NAME = "expedientes_clientes"
URL_EXPIRY = 3600  # 1 hora en segundos


class RevisionRequest(BaseModel):
    estado: str           # "APROBADO", "RECHAZADO" o "PENDIENTE"
    comentario: str = ""  # Opcional para aprobados, recomendado para rechazados


@router.get("/documentos/{doc_id}")
async def get_documento_detail(doc_id: str):
    """
    Devuelve el detalle de un documento específico + una URL firmada temporal
    para que el admin pueda abrirlo en el navegador sin descargarlo.
    """
    sb = get_supabase_admin()

    # Obtener documento con info de empresa
    table_name = "documentos_expediente"
    doc_resp = sb.table(table_name).select("*, empresas(nombre, rfc)").eq("id", doc_id).single().execute()
    
    if not doc_resp.data:
        # Intentar en la tabla de representantes
        table_name = "documentos_representante"
        doc_resp = sb.table(table_name).select("*, empresas(nombre, rfc)").eq("id", doc_id).single().execute()
        
    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc = doc_resp.data
    empresa_info = doc.pop("empresas", {}) or {}

    # Generar URL firmada para visualización (1 hora)
    signed_url = ""
    if doc.get("storage_path"):
        try:
            signed_resp = sb.storage.from_(BUCKET_NAME).create_signed_url(
                doc["storage_path"], expires_in=URL_EXPIRY
            )
            signed_url = signed_resp.get("signedURL") or signed_resp.get("signed_url", "")
        except Exception as e:
            logger.warning(f"No se pudo generar URL firmada para {doc_id}: {e}")

    return {
        **doc,
        "empresa_nombre": empresa_info.get("nombre", "Desconocida"),
        "empresa_rfc": empresa_info.get("rfc", ""),
        "url_documento": signed_url,
        "url_expira_en_segundos": URL_EXPIRY,
    }


@router.patch("/documentos/{doc_id}/revisar")
async def revisar_documento(
    doc_id: str,
    req: RevisionRequest,
):
    """
    Actualiza el estado de un documento tras la revisión del equipo admin.
    - APROBADO: El cliente verá su tarjeta en verde.
    - RECHAZADO: El cliente verá la tarjeta en rojo con el comentario explicando
                 qué está mal y podrá volver a subir el archivo.
    """

    estados_validos = ["APROBADO", "RECHAZADO", "PENDIENTE"]
    if req.estado not in estados_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Debe ser uno de: {estados_validos}"
        )

    if req.estado == "RECHAZADO" and not req.comentario.strip():
        raise HTTPException(
            status_code=400,
            detail="Al rechazar un documento debes incluir un comentario explicando el motivo."
        )

    sb = get_supabase_admin()

    # Verificar que el documento existe
    table_name = "documentos_expediente"
    doc_resp = sb.table(table_name).select("id, estado, tipo_documento, empresa_id").eq("id", doc_id).single().execute()
    
    if not doc_resp.data:
        table_name = "documentos_representante"
        doc_resp = sb.table(table_name).select("id, estado, tipo_documento, empresa_id").eq("id", doc_id).single().execute()

    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc_actual = doc_resp.data
    if doc_actual["estado"] not in ["PENDIENTE"]:
        logger.warning(f"Revisando documento con estado {doc_actual['estado']} (no PENDIENTE)")

    ahora = datetime.now(timezone.utc).isoformat()

    update_data = {
        "estado": req.estado,
        "comentario_admin": req.comentario.strip() if req.comentario else None,
        "revisado_en": ahora,
    }

    result = sb.table(table_name).update(update_data).eq("id", doc_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="No se pudo actualizar el documento")

    logger.info(
        f"Documento {doc_id} ({doc_actual['tipo_documento']}) → {req.estado} "
        f"por admin (interno)"
    )

    return {
        "message": f"Documento marcado como {req.estado}",
        "documento_id": doc_id,
        "tipo_documento": doc_actual["tipo_documento"],
        "empresa_id": doc_actual["empresa_id"],
        "estado": req.estado,
        "comentario": req.comentario,
        "revisado_en": ahora,
        "revisado_por": "admin (interno)",
    }
