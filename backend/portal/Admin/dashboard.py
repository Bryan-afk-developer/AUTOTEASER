"""
dashboard.py — Panel de control del equipo Admin.

Endpoint:
- GET /api/portal/admin/pendientes
  Devuelve todos los documentos en estado PENDIENTE agrupados por empresa.
- GET /api/portal/admin/empresas
  Lista todas las empresas con el resumen de su expediente.
"""
import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel

import concurrent.futures
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse

from portal.shared.supabase_db import get_supabase_admin
from portal.Cliente.expedientes import get_todos_los_documentos_requeridos, DOCUMENTOS_REPRESENTANTE

logger = logging.getLogger(__name__)
router = APIRouter()


# Auth removed for internal Intranet tool


@router.get("/pendientes")
async def get_pendientes(
    estado: str = Query(default="PENDIENTE", description="Filtrar por estado: PENDIENTE, APROBADO, RECHAZADO, FALTANTE, o ALL"),
):
    """
    Devuelve todos los documentos filtrados por estado, con info de la empresa.
    Por defecto devuelve solo los PENDIENTES (la bandeja de entrada del equipo).
    """

    sb = get_supabase_admin()

    # Query con join a empresas
    query = (
        sb.table("documentos_expediente")
        .select("*, empresas(id, nombre, rfc)")
        .order("subido_en", desc=True)
    )

    if estado != "ALL":
        query = query.eq("estado", estado)

    result = query.execute()
    documentos = result.data or []

    # Aplanar la respuesta para que el frontend la consuma fácilmente
    respuesta = []
    for doc in documentos:
        empresa_info = doc.pop("empresas", {}) or {}
        respuesta.append({
            **doc,
            "empresa_nombre": empresa_info.get("nombre", "Desconocida"),
            "empresa_rfc": empresa_info.get("rfc", ""),
        })

    # Estadísticas generales
    stats_resp = sb.table("documentos_expediente").select("estado").execute()
    stats_raw = stats_resp.data or []
    stats = {"PENDIENTE": 0, "APROBADO": 0, "RECHAZADO": 0}
    for row in stats_raw:
        estado_doc = row.get("estado", "")
        if estado_doc in stats:
            stats[estado_doc] += 1

    return {
        "documentos": respuesta,
        "total": len(respuesta),
        "filtro": estado,
        "estadisticas": stats,
    }


@router.get("/empresas")
async def get_empresas():
    """
    Lista todas las empresas registradas con el resumen de su expediente.
    Útil para la vista de 'todas las empresas' en el panel admin.
    """

    sb = get_supabase_admin()

    # Traer empresas
    empresas_resp = sb.table("empresas").select("*").order("created_at", desc=True).execute()
    empresas = empresas_resp.data or []

    # Para cada empresa, contar documentos por estado
    resultado = []
    for empresa in empresas:
        docs_resp = sb.table("documentos_expediente").select("estado").eq("empresa_id", empresa["id"]).execute()
        docs = docs_resp.data or []

        conteo = {"PENDIENTE": 0, "APROBADO": 0, "RECHAZADO": 0, "FALTANTE": 0}
        for doc in docs:
            est = doc.get("estado", "FALTANTE")
            if est in conteo:
                conteo[est] += 1

        resultado.append({
            "id": empresa["id"],
            "nombre": empresa["nombre"],
            "rfc": empresa.get("rfc"),
            "created_at": empresa.get("created_at"),
            "documentos_count": len(docs),
            "conteo_estados": conteo,
        })

    return {"empresas": resultado, "total": len(resultado)}

@router.get("/empresas/{empresa_id}/documentos")
async def get_empresa_documentos(empresa_id: str):
    """
    Devuelve todos los documentos de una empresa específica.
    """
    sb = get_supabase_admin()
    
    # Check si la empresa existe
    emp_resp = sb.table("empresas").select("nombre, rfc").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
        
    empresa_info = emp_resp.data
    
    docs_resp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).order("subido_en", desc=True).execute()
    docs_empresa = docs_resp.data or []
    
    rep_resp = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).order("subido_en", desc=True).execute()
    docs_representante = rep_resp.data or []
    
    docs_subidos = docs_empresa + docs_representante
    
    docs_subidos_dict = {d["tipo_documento"]: d for d in docs_subidos}
    
    # Obtener bancos para esta empresa
    bancos_resp = sb.table("cuentas_bancarias").select("*").eq("empresa_id", empresa_id).execute()
    bancos = bancos_resp.data or []
    
    documentos_requeridos = get_todos_los_documentos_requeridos(bancos)
    
    documentos_completos = []
    
    for doc_req in documentos_requeridos:
        clave = doc_req["clave"]
        doc_subido = docs_subidos_dict.get(clave)
        
        if doc_subido:
            # Add empresa info to the document
            doc_subido["empresa_nombre"] = empresa_info.get("nombre")
            doc_subido["empresa_rfc"] = empresa_info.get("rfc")
            doc_subido["nombre_esperado"] = doc_req["nombre"]
            doc_subido["grupo"] = doc_req.get("grupo", "empresa")
            
            # Update legacy database records with current folder info
            if doc_req.get("nombre_carpeta"):
                doc_subido["nombre_carpeta"] = doc_req["nombre_carpeta"]
            if doc_req.get("cuenta_bancaria_id"):
                doc_subido["cuenta_bancaria_id"] = doc_req["cuenta_bancaria_id"]
                
            documentos_completos.append(doc_subido)
        else:
            documentos_completos.append({
                "id": None,
                "empresa_id": empresa_id,
                "tipo_documento": clave,
                "nombre_esperado": doc_req["nombre"],
                "grupo": doc_req.get("grupo", "empresa"),
                "estado": "FALTANTE",
                "empresa_nombre": empresa_info.get("nombre"),
                "empresa_rfc": empresa_info.get("rfc"),
                "nombre_carpeta": doc_req.get("nombre_carpeta"),
                "cuenta_bancaria_id": doc_req.get("cuenta_bancaria_id"),
            })
            
    # Also include any documents uploaded that might not be in the current required list 
    # (e.g. if required list changed but they had old uploads)
    req_claves = {d["clave"] for d in documentos_requeridos}
    for doc_subido in docs_subidos:
        if doc_subido["tipo_documento"] not in req_claves:
            # Skip old legacy states of account that don't match the new slot logic (1 to 7)
            if doc_subido["tipo_documento"].startswith("ec_"):
                continue
                
            doc_subido["empresa_nombre"] = empresa_info.get("nombre")
            doc_subido["empresa_rfc"] = empresa_info.get("rfc")
            doc_subido["nombre_esperado"] = doc_subido.get("nombre_archivo", doc_subido["tipo_documento"])
            
            if doc_subido["tipo_documento"].startswith("declaracion_"):
                doc_subido["grupo"] = "declaraciones"
            elif doc_subido["tipo_documento"].startswith("otros_"):
                doc_subido["grupo"] = "otros"
            else:
                doc_subido["grupo"] = "empresa"
            
            documentos_completos.append(doc_subido)
        
    return {
        "empresa": empresa_info,
        "documentos": documentos_completos,
        "total": len(documentos_completos)
    }


CLAVES_REPRESENTANTE = {doc["clave"] for doc in DOCUMENTOS_REPRESENTANTE}


@router.get("/empresas/{empresa_id}/descargar-todo")
async def descargar_todos_documentos(empresa_id: str):
    """
    Descarga todos los documentos subidos de una empresa como un archivo ZIP.
    Estructura estricta para grupos corporativos.
    """
    sb = get_supabase_admin()

    emp_resp = sb.table("empresas").select("nombre").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_nombre = emp_resp.data["nombre"].strip()

    docs_exp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).execute()
    docs_rep = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).execute()
    todos_docs = (docs_exp.data or []) + (docs_rep.data or [])

    if not todos_docs:
        raise HTTPException(status_code=404, detail="No hay documentos subidos para esta empresa")
        
    # Obtener bancos (para saber el nombre de la carpeta bancaria de cada doc)
    bancos_resp = sb.table("cuentas_bancarias").select("id, nombre_banco").eq("empresa_id", empresa_id).execute()
    bancos_dict = {b["id"]: b["nombre_banco"] for b in bancos_resp.data or []}

    zip_buffer = io.BytesIO()
    ahora = datetime.now(timezone.utc).isoformat()
    archivos_incluidos = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # 1. GENERAR ESTRUCTURA VACÍA BASE
        carpetas_base = [
            f"{empresa_nombre}/1. REPRESENTANTES LEGALES/1. GENERALES/1. INE/",
            f"{empresa_nombre}/1. REPRESENTANTES LEGALES/1. GENERALES/2. CONSTANCIA SITUACION FISCAL/",
            f"{empresa_nombre}/1. REPRESENTANTES LEGALES/1. GENERALES/3. COMPROBANTE DOMICILIO/",
            f"{empresa_nombre}/1. REPRESENTANTES LEGALES/1. GENERALES/4. ACTA NACIMIENTO/",
            f"{empresa_nombre}/1. REPRESENTANTES LEGALES/1. GENERALES/5. ACTA MATRIMONIO/",
            f"{empresa_nombre}/1. REPRESENTANTES LEGALES/1. GENERALES/PREVIOS/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/0. PRE ANALISIS/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/1. ACTAS/ACTA CONSTITUTIVA/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/1. ACTAS/ACTAS DE ASAMBLEA/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/1. ACTAS/REGISTRO PUBLICO/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/2. ESTADOS FINANCIEROS/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/3. ESTADOS DE CUENTA/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/4. BURO DE CREDITO/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/5. DECLARACIONES/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/6. GENERALES/1. CONSTANCIA SITUACION FISCAL/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/6. GENERALES/2. COMPROBANTE DOMICILIO/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/6. GENERALES/3. OPINION DE CUMPLIMIENTO/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/6. GENERALES/4. FIEL/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/6. GENERALES/PREVIOS/",
            f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/7. OTROS/",
        ]
        # Crear carpetas de banco vacías
        for b_name in bancos_dict.values():
            carpetas_base.append(f"{empresa_nombre}/2. EMPRESAS DEL GRUPO/3. ESTADOS DE CUENTA/{b_name}/")
            
        for c in carpetas_base:
            zf.writestr(zipfile.ZipInfo(c), b'')

        rutas_agregadas = set()
        docs_a_bajar = []

        for doc in todos_docs:
            storage_path = doc.get("storage_path")
            if not storage_path:
                continue
                
            try:
                nombre_archivo = doc.get("nombre_archivo", storage_path.split("/")[-1])
                tipo = doc.get("tipo_documento", "doc")
                
                # ==== LÓGICA DE MAPEO DE CARPETAS ====
                # Directorio Raíz: GRUPO
                ruta_base = f"{empresa_nombre}/"
                ruta_final = ""
                
                if tipo in CLAVES_REPRESENTANTE:
                    rep_folder = "1. REPRESENTANTES LEGALES/1. GENERALES"
                    if tipo == "ine_representante":
                        ruta_final = f"{rep_folder}/1. INE/{nombre_archivo}"
                    elif tipo == "csf_representante":
                        ruta_final = f"{rep_folder}/2. CONSTANCIA SITUACION FISCAL/{nombre_archivo}"
                    elif tipo == "comprobante_domicilio_representante":
                        ruta_final = f"{rep_folder}/3. COMPROBANTE DOMICILIO/{nombre_archivo}"
                    elif tipo == "acta_matrimonio":
                        ruta_final = f"{rep_folder}/5. ACTA MATRIMONIO/{nombre_archivo}"
                    else:
                        ruta_final = f"{rep_folder}/PREVIOS/{nombre_archivo}"
                else:
                    emp_folder = "2. EMPRESAS DEL GRUPO"
                    if tipo == "curriculum_empresa":
                        ruta_final = f"{emp_folder}/0. PRE ANALISIS/{nombre_archivo}"
                    elif tipo == "acta_constitutiva":
                        ruta_final = f"{emp_folder}/1. ACTAS/ACTA CONSTITUTIVA/{nombre_archivo}"
                    elif tipo.startswith("financiero_eeff_"):
                        ruta_final = f"{emp_folder}/2. ESTADOS FINANCIEROS/{nombre_archivo}"
                    elif tipo.startswith("ec_"):
                        banco_id = doc.get("cuenta_bancaria_id")
                        nombre_banco = bancos_dict.get(banco_id, "BANCO DESCONOCIDO")
                        
                        if nombre_banco == "BANCO DESCONOCIDO":
                            continue
                        
                        import re
                        year_match = re.match(r"^(\d{4})\.\d{2}\s*-", nombre_archivo)
                        if year_match:
                            year_folder = year_match.group(1)
                            ruta_final = f"{emp_folder}/3. ESTADOS DE CUENTA/{nombre_banco}/{year_folder}/{nombre_archivo}"
                        else:
                            ruta_final = f"{emp_folder}/3. ESTADOS DE CUENTA/{nombre_banco}/{nombre_archivo}"
                    elif tipo == "buro_credito":
                        ruta_final = f"{emp_folder}/4. BURO DE CREDITO/{nombre_archivo}"
                    elif tipo.startswith("declaracion_"):
                        partes = tipo.split("_")
                        anio = partes[2] if len(partes) > 2 and partes[2].isdigit() else "AÑO DESCONOCIDO"
                        ruta_final = f"{emp_folder}/5. DECLARACIONES/{anio}/{nombre_archivo}"
                    elif tipo == "csf_empresa":
                        ruta_final = f"{emp_folder}/6. GENERALES/1. CONSTANCIA SITUACION FISCAL/{nombre_archivo}"
                    elif tipo == "comprobante_domicilio_empresa":
                        ruta_final = f"{emp_folder}/6. GENERALES/2. COMPROBANTE DOMICILIO/{nombre_archivo}"
                    elif tipo == "opinion_cumplimiento":
                        ruta_final = f"{emp_folder}/6. GENERALES/3. OPINION DE CUMPLIMIENTO/{nombre_archivo}"
                    elif tipo.startswith("otros_"):
                        ruta_final = f"{emp_folder}/7. OTROS/{nombre_archivo}"
                    else:
                        ruta_final = f"{emp_folder}/6. GENERALES/PREVIOS/{nombre_archivo}"
                
                zip_path = ruta_base + ruta_final
                
                # DEDUPLICAR
                if zip_path in rutas_agregadas:
                    continue
                rutas_agregadas.add(zip_path)
                docs_a_bajar.append({"zip_path": zip_path, "storage_path": storage_path, "id": doc["id"], "tipo": tipo})
            except Exception as e:
                logger.warning(f"Error procesando {storage_path}: {e}")
                continue

        def fetch_file(d):
            return d, sb.storage.from_("expedientes_clientes").download(d["storage_path"])
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futuros = [executor.submit(fetch_file, d) for d in docs_a_bajar]
            for future in concurrent.futures.as_completed(futuros):
                try:
                    d, file_bytes = future.result()
                    zf.writestr(d["zip_path"], file_bytes)
                    archivos_incluidos += 1
                    
                    table = "documentos_representante" if d["tipo"] in CLAVES_REPRESENTANTE else "documentos_expediente"
                    sb.table(table).update({
                        "descargado": True,
                        "descargado_en": ahora,
                    }).eq("id", d["id"]).execute()
                except Exception as e:
                    logger.warning(f"Error descargando ZIP: {e}")

    # Siempre permitimos descargar el ZIP aunque solo tenga las carpetas vacías (archivos_incluidos puede ser 0)
    zip_buffer.seek(0)
    safe_name = empresa_nombre.replace(" ", "_").replace("/", "-")
    filename = f"Expediente_{safe_name}.zip"

    logger.info(f"ZIP generado para {empresa_nombre}: {archivos_incluidos} archivos")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

class DescargarSeleccionRequest(BaseModel):
    doc_ids: List[str]

@router.post("/empresas/{empresa_id}/descargar-seleccion")
async def descargar_seleccion_documentos(empresa_id: str, req: DescargarSeleccionRequest):
    """
    Descarga una selección de documentos de una empresa como un archivo ZIP.
    Estructura estricta para grupos corporativos.
    """
    sb = get_supabase_admin()

    emp_resp = sb.table("empresas").select("nombre").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_nombre = emp_resp.data["nombre"].strip()

    docs_exp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).execute()
    docs_rep = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).execute()
    todos_docs = (docs_exp.data or []) + (docs_rep.data or [])

    if not todos_docs:
        raise HTTPException(status_code=404, detail="No hay documentos subidos para esta empresa")
        
    # Obtener bancos (para saber el nombre de la carpeta bancaria de cada doc)
    bancos_resp = sb.table("cuentas_bancarias").select("id, nombre_banco").eq("empresa_id", empresa_id).execute()
    bancos_dict = {b["id"]: b["nombre_banco"] for b in bancos_resp.data or []}

    zip_buffer = io.BytesIO()
    ahora = datetime.now(timezone.utc).isoformat()
    archivos_incluidos = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        rutas_agregadas = set()
        docs_a_bajar = []

        for doc in todos_docs:
            if str(doc.get("id")) not in req.doc_ids:
                continue

            storage_path = doc.get("storage_path")
            if not storage_path:
                continue
                
            nombre_archivo = doc.get("nombre_archivo", storage_path.split("/")[-1])
            tipo = doc.get("tipo_documento", "doc")
            
            # Al descargar una sección específica, usamos una estructura plana
            ruta_final = nombre_archivo

            if len(ruta_final) > 0:
                if ruta_final in rutas_agregadas:
                    partes = ruta_final.rsplit(".", 1)
                    if len(partes) == 2:
                        ruta_final = f"{partes[0]}_{archivos_incluidos}.{partes[1]}"
                    else:
                        ruta_final = f"{ruta_final}_{archivos_incluidos}"
                        
                rutas_agregadas.add(ruta_final)
                docs_a_bajar.append({"zip_path": ruta_final, "storage_path": storage_path, "id": doc["id"], "tipo": tipo})

        def fetch_file(d):
            return d, sb.storage.from_("expedientes_clientes").download(d["storage_path"])
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futuros = [executor.submit(fetch_file, d) for d in docs_a_bajar]
            for future in concurrent.futures.as_completed(futuros):
                try:
                    d, file_bytes = future.result()
                    zf.writestr(d["zip_path"], file_bytes)
                    archivos_incluidos += 1
                except Exception as e:
                    logger.warning(f"No se pudo descargar seleccion {d['storage_path']}: {e}")
                    continue

    if archivos_incluidos == 0:
        raise HTTPException(status_code=404, detail="No se pudo descargar ningún archivo de Storage")

    zip_buffer.seek(0)
    safe_name = empresa_nombre.replace(" ", "_").replace("/", "-")
    filename = f"Seleccion_{safe_name}.zip"

    logger.info(f"ZIP generado para {empresa_nombre} (Selección): {archivos_incluidos} archivos")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

import mimetypes

@router.get("/empresas/{empresa_id}/documentos/{doc_id}/descargar")
async def descargar_documento_individual(empresa_id: str, doc_id: str, is_rep: bool = False):
    """
    Descarga un archivo individual, marcándolo como descargado.
    """
    sb = get_supabase_admin()
    table = "documentos_representante" if is_rep else "documentos_expediente"
    
    doc_resp = sb.table(table).select("*").eq("id", doc_id).single().execute()
    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
        
    doc = doc_resp.data
    storage_path = doc.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=400, detail="El documento no tiene un archivo asociado")
        
    try:
        file_bytes = sb.storage.from_("expedientes_clientes").download(storage_path)
    except Exception as e:
        logger.error(f"Error descargando {storage_path}: {e}")
        raise HTTPException(status_code=500, detail="Error descargando de Storage")
        
    ahora = datetime.now(timezone.utc).isoformat()
    sb.table(table).update({
        "descargado": True,
        "descargado_en": ahora,
    }).eq("id", doc_id).execute()
    
    nombre_archivo = doc.get("nombre_archivo", storage_path.split("/")[-1])
    mime_type, _ = mimetypes.guess_type(nombre_archivo)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
