"""
upload.py — Subida de documentos al expediente del cliente.

Endpoints:
- POST /api/portal/cliente/subir-documento
  Recibe el PDF, lo sube a Supabase Storage y crea/actualiza la fila
  correspondiente en `documentos_expediente`.
- POST /api/portal/cliente/subir-estados-cuenta-auto
  Recibe múltiples PDFs, detecta el banco automáticamente y los asigna.
- PATCH /api/portal/cliente/mover-documento-banco
  Mueve un archivo de "No Reconocidos" a otra carpeta bancaria.
"""
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel
from typing import List

from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin
from portal.Cliente.expedientes import DOCUMENTOS_REPRESENTANTE, calcular_estados_de_cuenta

# Bank detection imports
try:
    import fitz  # PyMuPDF
    from app.bank_detector import detect_bank
    from app.banks import get_parser
    BANK_DETECTION_AVAILABLE = True
except ImportError:
    BANK_DETECTION_AVAILABLE = False

# SAT detection imports
try:
    from app.SAT.Detect_Sat_file import detect_sat_document
    from app.SAT.Opinion_Cumplimiento import matches as opc_matches, parse as opc_parse
    SAT_DETECTION_AVAILABLE = True
except ImportError:
    SAT_DETECTION_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter()

BUCKET_NAME = "expedientes_clientes"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


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

    # --- Opinión de Cumplimiento: detect POSITIVO/NEGATIVO and save in metadata ---
    requires_justification = False
    if tipo_documento == "opinion_cumplimiento" and SAT_DETECTION_AVAILABLE:
        try:
            text_opc = ""
            if BANK_DETECTION_AVAILABLE:
                import fitz as _fitz
                _doc = _fitz.open(stream=content, filetype="pdf")
                text_opc = " ".join(_page.get_text() for _page in _doc)
            if text_opc and opc_matches(text_opc):
                parsed_opc = opc_parse(text_opc)
                sentido = parsed_opc.get("sentido")
                if sentido:
                    # Guardamos el sentido como comentario técnico del sistema
                    doc_data["comentario_admin"] = f"[SISTEMA] OPC: {sentido}"
                    logger.info(f"Opinión de Cumplimiento detectada: {sentido}")
                    if sentido == "NEGATIVO":
                        requires_justification = True
        except Exception as e:
            logger.warning(f"No se pudo leer Opinión de Cumplimiento: {e}")

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
        "requires_justification": requires_justification,
    }


class JustificacionRequest(BaseModel):
    justificacion: str

@router.patch("/documentos/{doc_id}/justificar")
async def justificar_documento(
    doc_id: str,
    payload: JustificacionRequest,
    authorization: str = Header(None)
):
    """
    Guarda la justificación de un cliente para un documento (ej. OPC Negativa).
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()
    
    # Primero buscamos en expedientes
    doc_resp = sb.table("documentos_expediente").select("*").eq("id", doc_id).execute()
    table = "documentos_expediente"
    
    if not doc_resp.data:
        # Si no, buscamos en representante
        doc_resp = sb.table("documentos_representante").select("*").eq("id", doc_id).execute()
        table = "documentos_representante"
        if not doc_resp.data:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
            
    doc = doc_resp.data[0]
    
    # Concatenar a comentario_admin actual si existe
    comentario_actual = doc.get("comentario_admin") or ""
    nuevo_comentario = comentario_actual + f"\n\n[JUSTIFICACIÓN CLIENTE]:\n{payload.justificacion}"
    
    sb.table(table).update({
        "comentario_admin": nuevo_comentario.strip()
    }).eq("id", doc_id).execute()
    
    return {"message": "Justificación guardada exitosamente"}


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

    doc_resp = sb.table(table_name).select("*").eq("empresa_id", empresa_id).eq("tipo_documento", tipo_documento).execute()
    if not doc_resp.data:
        # Ya no existe en BD, podemos considerarlo eliminado exitosamente
        return {"message": f"Documento {tipo_documento} eliminado (ya no existía)"}

    docs_to_delete = doc_resp.data
    
    # Permitir borrar cualquier documento, incluso si está aprobado

    # Eliminar de Storage
    for doc in docs_to_delete:
        if doc.get("storage_path"):
            try:
                sb.storage.from_(BUCKET_NAME).remove([doc["storage_path"]])
            except Exception as e:
                logger.warning(f"Error eliminando de Storage (no crítico): {e}")

    # Eliminar de BD
    doc_ids = [d["id"] for d in docs_to_delete]
    sb.table(table_name).delete().in_("id", doc_ids).execute()

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.warning(f"Could not extract text from PDF: {e}")
        return ""


def _get_or_create_cuenta_bancaria(sb, empresa_id: str, nombre_banco: str) -> dict:
    """Find existing cuenta bancaria or create it if it doesn't exist."""
    existing = sb.table("cuentas_bancarias").select("*").eq("empresa_id", empresa_id).eq("nombre_banco", nombre_banco).execute()
    if existing.data:
        return existing.data[0]
    result = sb.table("cuentas_bancarias").insert({
        "empresa_id": empresa_id,
        "nombre_banco": nombre_banco
    }).execute()
    return result.data[0]


def _get_next_slot(sb, cuenta_bancaria_id: str, banco: dict) -> str | None:
    """Get the next available slot (ec_{id}_1 to ec_{id}_7) for a bank account."""
    slots_requeridos = calcular_estados_de_cuenta(banco)
    docs_actuales_resp = sb.table("documentos_expediente").select("tipo_documento, estado").eq("cuenta_bancaria_id", cuenta_bancaria_id).execute()
    ocupados = {}
    for d in (docs_actuales_resp.data or []):
        if d["estado"] not in ("FALTANTE", "RECHAZADO"):
            ocupados[d["tipo_documento"]] = True
    for slot in slots_requeridos:
        if slot["clave"] not in ocupados:
            return slot["clave"]
    return None


# ── Auto-detect upload ─────────────────────────────────────────────────────────

@router.post("/subir-estados-cuenta-auto")
async def subir_estados_cuenta_auto(
    files: List[UploadFile] = File(...),
    authorization: str = Header(None),
):
    """
    Recibe múltiples PDFs, detecta el banco automáticamente usando bank_detector
    y los asigna a la carpeta correspondiente.
    
    - PDFs reconocidos → se asignan al banco detectado (creando la carpeta si no existe)
    - PDFs no reconocidos → van a la carpeta especial "No Reconocidos"
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    ahora = datetime.now(timezone.utc).isoformat()
    resultados = []
    no_detectados = []

    BANCO_NOMBRES = {
        "hsbc": "HSBC",
        "bbva": "BBVA",
        "banorte": "Banorte",
        "santander": "Santander",
        "scotiabank": "Scotiabank",
        "banamex": "Banamex",
        "inbursa": "Inbursa",
        "sabadell": "Sabadell",
        "bxplus": "BX+",
    }

    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"Archivo demasiado grande: {file.filename}")
            no_detectados.append({"nombre": file.filename, "razon": "Archivo muy grande"})
            continue

        # Detect bank from text only (no Gemini)
        banco_key = None
        text = ""
        if BANK_DETECTION_AVAILABLE:
            try:
                text = _extract_text_from_pdf(content)
                banco_key = detect_bank(pdf_path=file.filename, text=text)
            except Exception as e:
                logger.error(f"Error detecting bank for {file.filename}: {e}")

        # Fallback to Gemini Vision if bank is not detected and it's available
        if not banco_key and BANK_DETECTION_AVAILABLE:
            try:
                from app.bank_detector import detect_bank_with_gemini
                banco_key = detect_bank_with_gemini(content)
            except Exception as e:
                logger.error(f"Gemini Vision failed for {file.filename}: {e}")

        # Extract account number using the bank parser
        account_suffix = None
        year = None
        month_num = None
        if banco_key and BANK_DETECTION_AVAILABLE:
            try:
                parser = get_parser(banco_key)
                if parser:
                    parsed = parser.parse(text, [text])
                    raw_account = parsed.get("account_name", "")
                    # raw_account is like "bbva0757" or "hsbc3456" — extract last digits
                    digits = ''.join(filter(str.isdigit, raw_account))
                    if digits:
                        account_suffix = digits[-4:]  # last 4 digits
                    
                    year = parsed.get("year")
                    month_raw = parsed.get("month", "").lower()
                    meses = {
                        'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
                        'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
                        'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
                    }
                    if month_raw in meses:
                        month_num = meses[month_raw]
                    elif month_raw.isdigit() and len(month_raw) <= 2:
                        month_num = month_raw.zfill(2)
            except Exception as e:
                logger.warning(f"Parser failed for {file.filename}: {e}")

        banco_display = BANCO_NOMBRES.get(banco_key, banco_key.upper()) if banco_key else "Desconocido"

        if banco_key and account_suffix:
            nombre_banco = f"{banco_display} - CUENTA ({banco_display.upper()} {account_suffix})"
        elif banco_key:
            nombre_banco = banco_display
        else:
            nombre_banco = "No Reconocidos"
            no_detectados.append({"nombre": file.filename, "razon": "Banco no identificado"})

        if year and month_num and account_suffix:
            nuevo_nombre_archivo = f"{year}.{month_num} - {banco_display.upper()} {account_suffix}.pdf"
        else:
            nuevo_nombre_archivo = file.filename

        # Get or create cuenta bancaria
        banco = _get_or_create_cuenta_bancaria(sb, empresa_id, nombre_banco)
        cuenta_bancaria_id = banco["id"]

        # Find next available slot
        next_slot = _get_next_slot(sb, cuenta_bancaria_id, banco)
        if not next_slot:
            # All 7 slots full — still upload but use a timestamp key
            next_slot = f"ec_{cuenta_bancaria_id}_{uuid.uuid4().hex[:6]}"

        # Upload to storage
        file_id = str(uuid.uuid4())[:8]
        storage_path = f"empresas/{empresa_id}/estados_cuenta/{nombre_banco}/{file_id}_{nuevo_nombre_archivo}"
        try:
            sb.storage.from_(BUCKET_NAME).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type or "application/octet-stream", "upsert": "true"},
            )
        except Exception as e:
            logger.error(f"Error uploading {file.filename}: {e}")
            err_msg = str(e)
            if "Payload too large" in err_msg or "exceeded the maximum allowed size" in err_msg:
                no_detectados.append({"nombre": file.filename, "razon": "Error de Supabase: El archivo supera el límite del bucket (Aumentarlo en tu panel de Supabase)"})
            else:
                no_detectados.append({"nombre": file.filename, "razon": "Error al guardar en la nube"})
            continue

        # Save to DB
        doc_data = {
            "empresa_id": empresa_id,
            "tipo_documento": next_slot,
            "nombre_archivo": nuevo_nombre_archivo,
            "storage_path": storage_path,
            "estado": "PENDIENTE",
            "comentario_admin": None,
            "subido_en": ahora,
            "revisado_en": None,
            "cuenta_bancaria_id": cuenta_bancaria_id,
            "nombre_carpeta": nombre_banco,
        }

        existing = sb.table("documentos_expediente").select("id").eq("empresa_id", empresa_id).eq("tipo_documento", next_slot).execute()
        if existing.data:
            sb.table("documentos_expediente").update(doc_data).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("documentos_expediente").insert(doc_data).execute()

        resultados.append({
            "nombre": file.filename,
            "banco": nombre_banco,
            "slot": next_slot,
        })

    return {
        "message": f"Procesados {len(files)} archivos",
        "detectados": resultados,
        "no_detectados": no_detectados,
    }


# ── Move document to another bank ─────────────────────────────────────────────

class MoverDocumentoRequest(BaseModel):
    documento_id: str
    cuenta_bancaria_destino_id: str


@router.patch("/mover-documento-banco")
async def mover_documento_banco(
    req: MoverDocumentoRequest,
    authorization: str = Header(None),
):
    """
    Mueve un documento de 'No Reconocidos' (o cualquier banco) a otra carpeta bancaria.
    Asigna el primer slot libre disponible en el banco destino.
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    # Get document
    doc_resp = sb.table("documentos_expediente").select("*").eq("id", req.documento_id).eq("empresa_id", empresa_id).single().execute()
    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    doc = doc_resp.data

    if doc["estado"] == "APROBADO":
        raise HTTPException(status_code=400, detail="No se puede mover un documento aprobado")

    # Get destination bank
    banco_dest_resp = sb.table("cuentas_bancarias").select("*").eq("id", req.cuenta_bancaria_destino_id).eq("empresa_id", empresa_id).single().execute()
    if not banco_dest_resp.data:
        raise HTTPException(status_code=404, detail="Cuenta bancaria destino no encontrada")
    banco_dest = banco_dest_resp.data
    nombre_banco_dest = banco_dest["nombre_banco"]

    # Find next slot in destination
    next_slot = _get_next_slot(sb, req.cuenta_bancaria_destino_id, banco_dest)
    if not next_slot:
        raise HTTPException(status_code=400, detail="No hay slots disponibles en la cuenta destino (ya tiene 7 archivos aceptados)")

    # Move file in storage (copy then delete old)
    old_path = doc.get("storage_path", "")
    file_id = str(uuid.uuid4())[:8]
    new_path = f"empresas/{empresa_id}/estados_cuenta/{nombre_banco_dest}/{file_id}_{doc.get('nombre_archivo', 'archivo.pdf')}"

    try:
        file_bytes = sb.storage.from_(BUCKET_NAME).download(old_path)
        sb.storage.from_(BUCKET_NAME).upload(
            path=new_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        sb.storage.from_(BUCKET_NAME).remove([old_path])
    except Exception as e:
        logger.error(f"Error moviendo archivo en storage: {e}")
        raise HTTPException(status_code=500, detail="Error al mover el archivo en Storage")

    # Update DB record
    sb.table("documentos_expediente").update({
        "tipo_documento": next_slot,
        "cuenta_bancaria_id": req.cuenta_bancaria_destino_id,
        "nombre_carpeta": nombre_banco_dest,
        "storage_path": new_path,
    }).eq("id", req.documento_id).execute()

    return {
        "message": f"Documento movido a {nombre_banco_dest}",
        "nuevo_slot": next_slot,
        "banco_destino": nombre_banco_dest,
    }


import unicodedata
import re

def sanitize_filename(filename: str) -> str:
    """Removes accents and special characters for Supabase storage compatibility."""
    text = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9_.-]', '_', text)
    return text


# ── SAT Auto-detect upload ───────────────────────────────────────────────────

@router.post("/subir-declaraciones-auto")
async def subir_declaraciones_auto(
    files: List[UploadFile] = File(...),
    authorization: str = Header(None),
):
    """
    Recibe múltiples PDFs del SAT, detecta automáticamente si es Acuse o Declaración
    y el año fiscal, luego los asigna a la carpeta correcta.

    Clave de documento: declaracion_acuse_{year} o declaracion_declaracion_{year}
    Solo acepta los últimos 3 años fiscales.
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    ahora = datetime.now(timezone.utc).isoformat()
    detectados = []
    no_detectados = []

    # Calculate valid years (last 3 fiscal years)
    from datetime import date
    hoy = date.today()
    if hoy.month >= 4:
        year_mas_reciente = hoy.year - 1
    else:
        year_mas_reciente = hoy.year - 2
    años_validos = {str(year_mas_reciente - i) for i in range(3)}

    for file in files:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            no_detectados.append({"nombre": file.filename, "razon": "Archivo muy grande"})
            continue

        # Extract text
        text = ""
        if BANK_DETECTION_AVAILABLE:
            try:
                text = _extract_text_from_pdf(content)
            except Exception as e:
                logger.warning(f"Error extracting text from {file.filename}: {e}")

        # Detect SAT document type (may fail if not readable or not SAT doc)
        sat_result = detect_sat_document(text) if (text and SAT_DETECTION_AVAILABLE) else {"tipo": None, "year": None}

        tipo = sat_result.get("tipo")  # "acuse" | "declaracion" | None
        year = sat_result.get("year")
        clasificado = bool(tipo and year)
        is_complementaria = sat_result.get("is_complementaria", False)

        if clasificado:
            if year not in años_validos:
                logger.warning(f"Año {year} fuera de los 3 años esperados, se sube de todas formas")

            # Build clave: declaracion_acuse_2025, declaracion_declaracion_2025
            # Or with comp: declaracion_acusecomp_2025
            # Build clave: declaracion_acuse_2025_uuid, declaracion_declaracion_2025_uuid
            # Or with comp: declaracion_acusecomp_2025_uuid
            uid = str(uuid.uuid4())[:8]
            tipo_clave_mid = f"{tipo}comp" if is_complementaria else tipo
            tipo_clave = f"declaracion_{tipo_clave_mid}_{year}_{uid}"
            
            if tipo == "acuse":
                tipo_display = "ACUSE_COMPLEMENTARIA" if is_complementaria else "ACUSE"
                nombre_base = "ACUSE_COMPLEMENTARIA" if is_complementaria else "ACUSE"
            else:
                tipo_display = "DECLARACION_COMPLEMENTARIA" if is_complementaria else "DECLARACION"
                nombre_base = "DECLARACIÓN_COMPLEMENTARIA" if is_complementaria else "DECLARACIÓN"
                
            nuevo_nombre = f"{nombre_base} {year}.pdf"
            safe_filename = sanitize_filename(file.filename)
            storage_path = f"empresas/{empresa_id}/declaraciones/{year}/{tipo_display}/{str(uuid.uuid4())[:8]}_{safe_filename}"
        else:
            # No se pudo clasificar → sube como "sin clasificar" para revisión del admin
            uid = str(uuid.uuid4())[:8]
            tipo_clave = f"declaracion_sinclasificar_{uid}"
            nuevo_nombre = file.filename
            safe_filename = sanitize_filename(file.filename)
            storage_path = f"empresas/{empresa_id}/declaraciones/sin_clasificar/{uid}_{safe_filename}"

        # Upload to storage
        try:
            sb.storage.from_(BUCKET_NAME).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type or "application/pdf", "upsert": "true"},
            )
        except Exception as e:
            logger.error(f"Error uploading SAT file {file.filename}: {e}")
            no_detectados.append({"nombre": file.filename, "razon": "Error al guardar en la nube"})
            continue

        doc_data = {
            "empresa_id": empresa_id,
            "tipo_documento": tipo_clave,
            "nombre_archivo": nuevo_nombre,
            "storage_path": storage_path,
            "estado": "PENDIENTE",
            "comentario_admin": None,
            "subido_en": ahora,
            "revisado_en": None,
        }

        # Para declaraciones no hay límite, siempre se inserta como nuevo registro
        sb.table("documentos_expediente").insert(doc_data).execute()

        if clasificado:
            detectados.append({
                "nombre": file.filename,
                "tipo": tipo_display,
                "year": year,
                "clave": tipo_clave,
            })
        else:
            no_detectados.append({
                "nombre": file.filename,
                "razon": "No se identificó automáticamente — guardado para revisión",
                "guardado": True,
            })

    return {
        "message": f"Procesados {len(files)} archivos SAT",
        "detectados": detectados,
        "no_detectados": no_detectados,
    }


# ── SAT Manual assignment (save unclassified to a chosen slot) ────────────────────

@router.post("/subir-declaracion-manual")
async def subir_declaracion_manual(
    tipo: str = Form(...),      # "acuse" | "declaracion"
    year: str = Form(...),      # "2025", "2024", "2023"
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """
    Sube un PDF del SAT asignando manualmente su tipo (acuse/declaracion) y año.
    Usado cuando la detección automática falla.
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    if tipo not in ("acuse", "declaracion"):
        raise HTTPException(status_code=400, detail="tipo debe ser 'acuse' o 'declaracion'")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Archivo muy grande")

    tipo_clave = f"declaracion_{tipo}_{year}"
    tipo_folder = "ACUSE" if tipo == "acuse" else "DECLARACION"
    nuevo_nombre = f"{tipo_folder}_{year}_{file.filename}"
    
    safe_filename = sanitize_filename(file.filename)
    storage_path = f"empresas/{empresa_id}/declaraciones/{year}/{tipo_folder}/{str(uuid.uuid4())[:8]}_{safe_filename}"

    try:
        sb.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "application/pdf", "upsert": "true"},
        )
    except Exception as e:
        logger.error(f"Error uploading SAT manual file: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar en la nube")

    ahora = datetime.now(timezone.utc).isoformat()
    doc_data = {
        "empresa_id": empresa_id,
        "tipo_documento": tipo_clave,
        "nombre_archivo": nuevo_nombre,
        "storage_path": storage_path,
        "estado": "PENDIENTE",
        "comentario_admin": None,
        "subido_en": ahora,
        "revisado_en": None,
    }

    existing = sb.table("documentos_expediente").select("id").eq("empresa_id", empresa_id).eq("tipo_documento", tipo_clave).execute()
    if existing.data:
        sb.table("documentos_expediente").update(doc_data).eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("documentos_expediente").insert(doc_data).execute()

    return {
        "message": f"Documento guardado como {tipo_folder} {year}",
        "tipo": tipo_folder,
        "year": year,
        "clave": tipo_clave,
    }
