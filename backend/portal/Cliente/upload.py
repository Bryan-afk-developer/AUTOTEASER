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
from typing import List

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin
from portal.Cliente.expedientes import DOCUMENTOS_REPRESENTANTE, calcular_estados_de_cuenta

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

    # 4. Determinar si es de banco y su path
    nombre_carpeta = None
    cuenta_bancaria_id = None
    
    if tipo_documento.startswith("ec_"):
        partes = tipo_documento.split("_")
        if len(partes) >= 4:
            cuenta_bancaria_id = partes[1]
            banco_resp = sb.table("cuentas_bancarias").select("nombre_banco").eq("id", cuenta_bancaria_id).single().execute()
            if banco_resp.data:
                nombre_carpeta = banco_resp.data["nombre_banco"]
    
    file_id = str(uuid.uuid4())[:8]
    if nombre_carpeta:
        storage_path = f"empresas/{empresa_id}/estados_cuenta/{nombre_carpeta}/{file_id}_{file.filename}"
    else:
        storage_path = f"empresas/{empresa_id}/{tipo_documento}/{file_id}_{file.filename}"

    # 5. Subir a Supabase Storage
    try:
        upload_response = sb.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "application/octet-stream", "upsert": "true"},
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
    
    if cuenta_bancaria_id:
        doc_data["cuenta_bancaria_id"] = cuenta_bancaria_id
    if nombre_carpeta:
        doc_data["nombre_carpeta"] = nombre_carpeta

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

@router.post("/subir-documentos-banco")
async def subir_documentos_banco(
    cuenta_bancaria_id: str = Form(...),
    files: List[UploadFile] = File(...),
    authorization: str = Header(None),
):
    """
    Sube múltiples PDFs a la vez para una cuenta bancaria.
    Busca los slots faltantes o rechazados y asigna los archivos en orden.
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    # 1. Validar empresa
    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    # 2. Validar banco
    banco_resp = sb.table("cuentas_bancarias").select("*").eq("id", cuenta_bancaria_id).eq("empresa_id", empresa_id).single().execute()
    if not banco_resp.data:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    banco = banco_resp.data
    nombre_carpeta = banco["nombre_banco"]

    # 3. Calcular slots requeridos y ver cuáles faltan/pueden ser reemplazados
    slots_requeridos = calcular_estados_de_cuenta(banco)
    
    # Obtener documentos actuales para este banco
    docs_actuales_resp = sb.table("documentos_expediente").select("*").eq("cuenta_bancaria_id", cuenta_bancaria_id).execute()
    docs_actuales = {d["tipo_documento"]: d for d in docs_actuales_resp.data or []}

    slots_disponibles = []
    for slot in slots_requeridos:
        doc = docs_actuales.get(slot["clave"])
        if not doc or doc["estado"] in ["FALTANTE", "RECHAZADO"]:
            slots_disponibles.append(slot["clave"])

    if not slots_disponibles:
        raise HTTPException(status_code=400, detail="No hay meses pendientes de subir para esta cuenta")

    if len(files) > len(slots_disponibles):
        raise HTTPException(status_code=400, detail=f"Enviaste {len(files)} archivos, pero solo faltan {len(slots_disponibles)} meses")

    ahora = datetime.now(timezone.utc).isoformat()
    resultados = []

    # 4. Procesar archivos asignándolos a los slots disponibles
    for i, file in enumerate(files):
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            continue # Saltar archivos gigantes
            
        tipo_documento = slots_disponibles[i]
        file_id = str(uuid.uuid4())[:8]
        storage_path = f"empresas/{empresa_id}/estados_cuenta/{nombre_carpeta}/{file_id}_{file.filename}"

        # Subir a storage
        try:
            sb.storage.from_(BUCKET_NAME).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type or "application/octet-stream", "upsert": "true"},
            )
        except Exception as e:
            logger.error(f"Error subiendo a Storage: {e}")
            continue

        doc_data = {
            "empresa_id": empresa_id,
            "tipo_documento": tipo_documento,
            "nombre_archivo": file.filename,
            "storage_path": storage_path,
            "estado": "PENDIENTE",
            "comentario_admin": None,
            "subido_en": ahora,
            "revisado_en": None,
            "cuenta_bancaria_id": cuenta_bancaria_id,
            "nombre_carpeta": nombre_carpeta
        }

        # Guardar en BD
        existing = docs_actuales.get(tipo_documento)
        if existing:
            sb.table("documentos_expediente").update(doc_data).eq("id", existing["id"]).execute()
        else:
            sb.table("documentos_expediente").insert(doc_data).execute()
            
        resultados.append(file.filename)

    return {
        "message": f"Se subieron {len(resultados)} archivos exitosamente",
        "archivos": resultados
    }
