"""
upload.py — Subida de documentos al expediente del cliente.

Endpoint:
- POST /api/portal/cliente/subir-documento
  Recibe el PDF, lo sube a Supabase Storage y crea/actualiza la fila
  correspondiente en `documentos_expediente`.
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin
from portal.Cliente.expedientes import DOCUMENTOS_REPRESENTANTE

logger = logging.getLogger(__name__)
router = APIRouter()

BUCKET_NAME = "expedientes_clientes"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/subir-documento")
async def subir_documento(
    tipo_documento: str = Form(...),
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """
    Sube un PDF al bucket de Supabase Storage y registra el documento en la BD.

    Si ya existe un documento para ese tipo (ej. después de un rechazo),
    lo reemplaza y vuelve a poner el estado en PENDIENTE.

    Args:
        tipo_documento: Clave del tipo de documento (ej. "acta_constitutiva",
                        "estado_cuenta_2025_04").
        file: Archivo PDF a subir.
    """
    # 1. Verificar autenticación
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    # 2. Validar archivo
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo demasiado grande. Máximo: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # 3. Obtener empresa del usuario
    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada para este usuario")
    empresa_id = empresa_resp.data["id"]

    # 4. Construir ruta en Storage: empresas/{empresa_id}/{tipo_documento}/{uuid}.pdf
    file_id = str(uuid.uuid4())[:8]
    storage_path = f"empresas/{empresa_id}/{tipo_documento}/{file_id}_{file.filename}"

    # 5. Subir a Supabase Storage
    try:
        upload_response = sb.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        logger.info(f"Archivo subido a Storage: {storage_path}")
    except Exception as e:
        logger.error(f"Error subiendo a Supabase Storage: {e}")
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

    # 6. Obtener URL del documento (URL firmada de 7 días para acceso del admin)
    try:
        signed_url_resp = sb.storage.from_(BUCKET_NAME).create_signed_url(storage_path, expires_in=604800)
        storage_url = signed_url_resp.get("signedURL") or signed_url_resp.get("signed_url", "")
    except Exception as e:
        logger.warning(f"No se pudo generar URL firmada: {e}")
        storage_url = ""

    # 7. Verificar a qué tabla pertenece (Representante o Empresa)
    claves_rep = {doc["clave"] for doc in DOCUMENTOS_REPRESENTANTE}
    table_name = "documentos_representante" if tipo_documento in claves_rep else "documentos_expediente"

    ahora = datetime.now(timezone.utc).isoformat()
    existing = sb.table(table_name).select("id").eq("empresa_id", empresa_id).eq("tipo_documento", tipo_documento).execute()

    doc_data = {
        "empresa_id": empresa_id,
        "tipo_documento": tipo_documento,
        "nombre_archivo": file.filename,
        "storage_path": storage_path,
        "estado": "PENDIENTE",
        "comentario_admin": None,  # Limpia comentarios previos al re-subir
        "subido_en": ahora,
        "revisado_en": None,
    }

    if existing.data:
        # Actualizar registro existente
        doc_id = existing.data[0]["id"]
        result = sb.table(table_name).update(doc_data).eq("id", doc_id).execute()
        accion = "actualizado"
    else:
        # Crear nuevo registro
        result = sb.table(table_name).insert(doc_data).execute()
        doc_id = result.data[0]["id"] if result.data else None
        accion = "creado"

    if not result.data:
        raise HTTPException(status_code=500, detail="El archivo se subió pero falló el registro en la base de datos")

    logger.info(f"Documento {accion}: empresa={empresa_id}, tipo={tipo_documento}, id={doc_id}")

    return {
        "message": f"Documento subido exitosamente",
        "documento_id": doc_id,
        "tipo_documento": tipo_documento,
        "nombre_archivo": file.filename,
        "estado": "PENDIENTE",
        "storage_path": storage_path,
        "subido_en": ahora,
    }


@router.delete("/eliminar-documento/{tipo_documento}")
async def eliminar_documento(
    tipo_documento: str,
    authorization: str = Header(None),
):
    """Elimina un documento del expediente (solo si está en FALTANTE o RECHAZADO)."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    claves_rep = {doc["clave"] for doc in DOCUMENTOS_REPRESENTANTE}
    table_name = "documentos_representante" if tipo_documento in claves_rep else "documentos_expediente"

    doc_resp = sb.table(table_name).select("*").eq("empresa_id", empresa_id).eq("tipo_documento", tipo_documento).single().execute()
    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc = doc_resp.data
    if doc["estado"] == "APROBADO":
        raise HTTPException(status_code=403, detail="No se puede eliminar un documento ya aprobado")

    # Eliminar de Storage
    try:
        sb.storage.from_(BUCKET_NAME).remove([doc["storage_path"]])
    except Exception as e:
        logger.warning(f"Error eliminando de Storage (no crítico): {e}")

    # Eliminar de BD
    sb.table(table_name).delete().eq("id", doc["id"]).execute()

    return {"message": f"Documento {tipo_documento} eliminado"}
