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
import uuid
import zipfile
from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel

import concurrent.futures
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse

from portal.shared.supabase_db import get_supabase_admin
from portal.Cliente.expedientes import get_todos_los_documentos_requeridos, DOCUMENTOS_REPRESENTANTE
from portal.Cliente.accionistas import DOCUMENTOS_ACCIONISTA
from portal.Cliente.sub_empresas import DOCUMENTOS_SUB_EMPRESA
from app.Buro_Credito.mop_extractor import extraer_mops_desde_storage
import re
import time

def format_generales_filename(tipo: str, original_name: str, is_rep: bool = False, person_name: str = None, ine_name: str = None) -> str:
    """
    Format names for '6. GENERALES' section and Individuals.
    """
    import re
    # Si el archivo ya tiene el formato correcto (ej: "2. CSF - NOMBRE - FECHA.pdf"), no lo arruinamos.
    if re.match(r"^[1-5]\.\s+(INE|CSF|CD|ACTA NACIMIENTO|ACTA MATRIMONIO|OPC|FIEL|CONSTANCIA)\b", original_name, re.IGNORECASE):
        return original_name

    ext = ""
    if "." in original_name:
        partes = original_name.rsplit(".", 1)
        ext = "." + partes[-1]
        
    date_str = ""
    import re
    match = re.search(r"(\d{4})[.-](\d{2})[.-](\d{2})", original_name)
    if match:
        date_str = f" - {match.group(1)}.{match.group(2)}.{match.group(3)}"
        
    name_suffix = f" - {person_name.strip().upper()}" if person_name else ""
    is_individual = is_rep or tipo.endswith("_accionista") or tipo == "acta_matrimonio"
    
    if tipo in ("ine_representante", "ine_accionista", "identificacion_representante", "identificacion_accionista"):
        final_ine_name = ine_name if ine_name else person_name
        name_suffix = f" - {final_ine_name.strip().upper()}" if final_ine_name else ""
        return f"1. INE{name_suffix}{ext}"
        
    elif tipo in ("csf_empresa", "csf_representante", "csf_accionista"):
        if is_individual:
            return f"2. CSF{name_suffix}{date_str}{ext}"
        else:
            if date_str: return f"1. CSF - PM{date_str}{ext}"
            return f"CONSTANCIA SITUACION FISCAL{ext}"
            
    elif tipo in ("comprobante_domicilio_empresa", "comprobante_domicilio_representante", "comprobante_domicilio_accionista"):
        if is_individual:
            return f"3. CD{name_suffix}{date_str}{ext}"
        else:
            if date_str: return f"2. CD - PM{date_str}{ext}"
            return f"COMPROBANTE DOMICILIO{ext}"
            
    elif tipo in ("acta_nacimiento_representante", "acta_nacimiento_accionista", "acta_nacimiento"):
        return f"4. ACTA NACIMIENTO{name_suffix}{ext}"
        
    elif tipo in ("acta_matrimonio", "acta_matrimonio_accionista"):
        return f"5. ACTA MATRIMONIO{name_suffix}{ext}"
        
    elif tipo == "opinion_cumplimiento":
        if date_str: return f"3. OPC - PM{date_str}{ext}"
        return f"OPINION DE CUMPLIMIENTO{ext}"
        
    elif tipo in ("fiel_empresa", "fiel_representante", "fiel_accionista", "fiel"):
        if is_individual:
            return f"FIEL{name_suffix}{date_str}{ext}"
        else:
            if date_str: return f"4. FIEL - PM{date_str}{ext}"
            return f"FIEL{ext}"
            
    return original_name

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


class CrearEmpresaRequest(BaseModel):
    nombre: str
    rfc: str | None = None

@router.post("/empresas")
async def crear_empresa(req: CrearEmpresaRequest):
    sb = get_supabase_admin()
    empresa_data = {
        "nombre": req.nombre,
        "rfc": req.rfc,
        "user_id": str(uuid.uuid4())  # UUID único por empresa, sin login
    }
    try:
        db_response = sb.table("empresas").insert(empresa_data).execute()
        if not db_response.data:
            raise HTTPException(status_code=500, detail="Error al guardar empresa")
        return db_response.data[0]
    except Exception as e:
        logger.error(f"Error creando empresa: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/empresas/{empresa_id}")
async def eliminar_empresa(empresa_id: str):
    sb = get_supabase_admin()
    try:
        db_response = sb.table("empresas").delete().eq("id", empresa_id).execute()
        # En Supabase v2, delete().execute() puede retornar data=[] si no encuentra nada o si no se usa .select()
        # Así que mejor no dependemos de db_response.data para el 404. Asumimos éxito si no lanza excepción.
        return {"success": True, "message": "Empresa eliminada exitosamente"}
    except Exception as e:
        logger.error(f"Error eliminando empresa: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/empresas")
async def get_empresas():
    """
    Lista todas las empresas registradas con el resumen de su expediente.
    Útil para la vista de 'todas las empresas' en el panel admin.
    """
    t0 = time.time()
    sb = get_supabase_admin()

    # Traer empresas
    empresas_resp = sb.table("empresas").select("*").order("created_at", desc=True).execute()
    empresas = empresas_resp.data or []
    t1 = time.time()

    # Traer todos los estados de documentos de UNA sola vez
    docs_resp = sb.table("documentos_expediente").select("empresa_id, estado").execute()
    docs = docs_resp.data or []
    
    docs_rep = sb.table("documentos_representante").select("empresa_id, estado").execute()
    docs.extend(docs_rep.data or [])
    
    docs_acc = sb.table("documentos_accionista").select("empresa_id, estado").execute()
    docs.extend(docs_acc.data or [])
    
    t2 = time.time()

    # Agrupar por empresa
    docs_por_empresa = {}
    for doc in docs:
        emp_id = doc["empresa_id"]
        est = doc.get("estado", "FALTANTE")
        if emp_id not in docs_por_empresa:
            docs_por_empresa[emp_id] = {"count": 0, "conteo": {"PENDIENTE": 0, "APROBADO": 0, "RECHAZADO": 0, "FALTANTE": 0}}
        
        docs_por_empresa[emp_id]["count"] += 1
        if est in docs_por_empresa[emp_id]["conteo"]:
            docs_por_empresa[emp_id]["conteo"][est] += 1
            
    t3 = time.time()

    # Construir resultado
    resultado = []
    for empresa in empresas:
        emp_id = empresa["id"]
        stats = docs_por_empresa.get(emp_id, {"count": 0, "conteo": {"PENDIENTE": 0, "APROBADO": 0, "RECHAZADO": 0, "FALTANTE": 0}})

        resultado.append({
            "id": emp_id,
            "nombre": empresa["nombre"],
            "rfc": empresa.get("rfc"),
            "created_at": empresa.get("created_at"),
            "documentos_count": stats["count"],
            "conteo_estados": stats["conteo"],
        })
        
    t4 = time.time()
    logger.info(f"PERF /empresas: DB Empresas={((t1-t0)*1000):.1f}ms, DB Docs={((t2-t1)*1000):.1f}ms, Group={((t3-t2)*1000):.1f}ms, Build={((t4-t3)*1000):.1f}ms, Total={((t4-t0)*1000):.1f}ms")

    return {"empresas": resultado, "total": len(resultado)}

@router.get("/empresas/{empresa_id}/documentos")
async def get_empresa_documentos(empresa_id: str):
    """
    Devuelve todos los documentos de una empresa específica.
    """
    t0 = time.time()
    sb = get_supabase_admin()
    
    # Check si la empresa existe
    emp_resp = sb.table("empresas").select("nombre, rfc").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
        
    empresa_info = emp_resp.data
    t1 = time.time()
    
    docs_resp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).order("subido_en", desc=True).execute()
    docs_empresa = docs_resp.data or []
    t2 = time.time()
    
    rep_resp = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).order("subido_en", desc=True).execute()
    docs_representante = rep_resp.data or []
    t3 = time.time()
    
    # Agregar accionistas
    acc_resp = sb.table("documentos_accionista").select("*").eq("empresa_id", empresa_id).order("subido_en", desc=True).execute()
    docs_accionista = acc_resp.data or []
    t4 = time.time()
    
    docs_subidos = docs_empresa + docs_representante + docs_accionista
    
    docs_subidos_dict = {d["tipo_documento"]: d for d in docs_subidos}
    
    # Obtener bancos para esta empresa
    bancos_resp = sb.table("cuentas_bancarias").select("*").eq("empresa_id", empresa_id).execute()
    bancos = bancos_resp.data or []
    t5 = time.time()
    
    documentos_requeridos = get_todos_los_documentos_requeridos(bancos, docs_subidos_dict)
    
    # Get accionistas (individuals) to build their UI entries properly
    accionistas_db_resp = sb.table("accionistas").select("*").eq("empresa_id", empresa_id).execute()
    accionistas_db = accionistas_db_resp.data or []
    t6 = time.time()
    
    documentos_completos = []
    
    # Expediente
    for req in documentos_requeridos:
        clave = req["clave"]
        doc_subido = docs_subidos_dict.get(clave)
        
        grupo_label = req.get("grupo")
        
        if doc_subido:
            doc_subido["nombre_esperado"] = req["nombre"]
            doc_subido["grupo"] = grupo_label
            doc_subido["empresa_nombre"] = empresa_info.get("nombre")
            doc_subido["empresa_rfc"] = empresa_info.get("rfc")
            documentos_completos.append(doc_subido)
        else:
            documentos_completos.append({
                "id": None,
                "empresa_id": empresa_id,
                "tipo_documento": clave,
                "nombre_esperado": req["nombre"],
                "grupo": grupo_label,
                "estado": "FALTANTE",
                "empresa_nombre": empresa_info.get("nombre"),
                "empresa_rfc": empresa_info.get("rfc")
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
        
    # ---------------------------------------------------------
    # Accionistas
    # ---------------------------------------------------------
    acc_resp = sb.table("accionistas").select("*").eq("empresa_id", empresa_id).order("orden").execute()
    accionistas = acc_resp.data or []
    
    docs_acc_resp = sb.table("documentos_accionista").select("*").eq("empresa_id", empresa_id).execute()
    docs_acc = docs_acc_resp.data or []
    docs_acc_dict = {f"{d['accionista_id']}_{d['tipo_documento']}": d for d in docs_acc}

    for acc in accionistas:
        acc_name = acc.get("nombre") or f"Accionista {acc['orden']}"
        grupo_label = "accionistas"
        
        for req in DOCUMENTOS_ACCIONISTA:
            clave = req["clave"]
            doc_key = f"{acc['id']}_{clave}"
            doc_subido = docs_acc_dict.get(doc_key)
            
            if doc_subido:
                doc_subido["empresa_nombre"] = empresa_info.get("nombre")
                doc_subido["empresa_rfc"] = empresa_info.get("rfc")
                doc_subido["nombre_esperado"] = req["nombre"]
                doc_subido["grupo"] = grupo_label
                doc_subido["nombre_carpeta"] = acc_name
                documentos_completos.append(doc_subido)
            else:
                documentos_completos.append({
                    "id": None,
                    "empresa_id": empresa_id,
                    "tipo_documento": clave,
                    "nombre_esperado": req["nombre"],
                    "grupo": grupo_label,
                    "estado": "FALTANTE",
                    "empresa_nombre": empresa_info.get("nombre"),
                    "empresa_rfc": empresa_info.get("rfc"),
                    "nombre_carpeta": acc_name,
                    "accionista_id": acc["id"]
                })
        
    # ---------------------------------------------------------
    # Sub Empresas (Aval / Grupo)
    # ---------------------------------------------------------
    sub_resp = sb.table("sub_empresas").select("*").eq("empresa_id", empresa_id).order("orden").execute()
    sub_empresas = sub_resp.data or []
    
    docs_sub_resp = sb.table("documentos_sub_empresa").select("*").eq("empresa_id", empresa_id).execute()
    docs_sub = docs_sub_resp.data or []
    docs_sub_dict = {f"{d['sub_empresa_id']}_{d['tipo_documento']}": d for d in docs_sub}

    for sub in sub_empresas:
        sub_name = sub.get("nombre") or f"Sub Empresa {sub['orden']}"
        grupo_label = "sub_empresas"
        
        for req in DOCUMENTOS_SUB_EMPRESA:
            clave = req["clave"]
            doc_subido = docs_sub_dict.get(f"{sub['id']}_{clave}")
            
            if doc_subido:
                doc_subido["nombre_esperado"] = req["nombre"]
                doc_subido["grupo"] = grupo_label
                doc_subido["empresa_nombre"] = sub_name
                doc_subido["empresa_rfc"] = sub.get("rfc")
                doc_subido["nombre_carpeta"] = sub_name
                documentos_completos.append(doc_subido)
            else:
                documentos_completos.append({
                    "id": None,
                    "empresa_id": empresa_id,
                    "sub_empresa_id": sub["id"],
                    "tipo_documento": clave,
                    "nombre_esperado": req["nombre"],
                    "grupo": grupo_label,
                    "estado": "FALTANTE",
                    "empresa_nombre": sub_name,
                    "empresa_rfc": sub.get("rfc"),
                    "nombre_carpeta": sub_name
                })

    t7 = time.time()
    logger.info(f"PERF /empresas/{empresa_id}/documentos: Emp={((t1-t0)*1000):.1f}ms, DocsExp={((t2-t1)*1000):.1f}ms, DocsRep={((t3-t2)*1000):.1f}ms, DocsAcc={((t4-t3)*1000):.1f}ms, Bancos={((t5-t4)*1000):.1f}ms, Accionistas={((t6-t5)*1000):.1f}ms, Build={((t7-t6)*1000):.1f}ms, Total={((t7-t0)*1000):.1f}ms")

    alerta_nombres_mismatch = False
    ine_doc = docs_subidos_dict.get("ine_representante")
    csf_doc = docs_subidos_dict.get("csf_representante")
    if ine_doc and csf_doc:
        n_ine = (ine_doc.get("extracted_data") or {}).get("nombre_extraido", "")
        n_csf = (csf_doc.get("extracted_data") or {}).get("nombre_extraido", "")
        if n_ine and n_csf:
            import unicodedata
            import re
            def _norm(name):
                name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
                return re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z0-9\s]', '', name)).strip().upper()
            if _norm(n_ine) != _norm(n_csf):
                alerta_nombres_mismatch = True

    return {
        "empresa": empresa_info,
        "accionistas": accionistas,
        "sub_empresas": sub_empresas,
        "bancos": bancos,
        "documentos": documentos_completos,
        "total": len(documentos_completos),
        "acta_principal": None,
        "alerta_nombres_mismatch": alerta_nombres_mismatch
    }


CLAVES_REPRESENTANTE = {doc["clave"] for doc in DOCUMENTOS_REPRESENTANTE}


@router.get("/empresas/{empresa_id}/descargar-todo")
async def descargar_todos_documentos(empresa_id: str):
    """
    Descarga todos los documentos subidos de una empresa como un archivo ZIP.
    Estructura estricta para grupos corporativos.
    """
    sb = get_supabase_admin()

    emp_resp = sb.table("empresas").select("nombre, representante_legal").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_nombre = emp_resp.data["nombre"].strip()
    
    rep_name = emp_resp.data.get("representante_legal")
    rep_folder = f"1.1 {rep_name.upper()}" if rep_name else "1.1 REPRESENTANTE LEGAL"

    docs_exp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).execute()
    docs_rep = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).execute()
    docs_acc = sb.table("documentos_accionista").select("*").eq("empresa_id", empresa_id).execute()
    docs_sub = sb.table("documentos_sub_empresa").select("*").eq("empresa_id", empresa_id).execute()
    
    # We also need accionistas and sub_empresas to know their names
    acc_resp = sb.table("accionistas").select("id, nombre, orden").eq("empresa_id", empresa_id).order("orden").execute()
    accionistas_dict = {a["id"]: a.get("nombre") or f"Accionista {a['orden']}" for a in acc_resp.data or []}

    sub_resp = sb.table("sub_empresas").select("id, nombre, orden, rol").eq("empresa_id", empresa_id).order("orden").execute()
    
    todos_docs = (docs_exp.data or []) + (docs_rep.data or []) + (docs_acc.data or []) + (docs_sub.data or [])

    if not todos_docs:
        raise HTTPException(status_code=404, detail="No hay documentos subidos para esta empresa")
        
    # Obtener bancos (para saber el nombre de la carpeta bancaria de cada doc)
    bancos_resp = sb.table("cuentas_bancarias").select("id, nombre_banco").eq("empresa_id", empresa_id).execute()
    bancos_dict = {b["id"]: b["nombre_banco"] for b in bancos_resp.data or []}

    zip_buffer = io.BytesIO()
    ahora = datetime.now(timezone.utc).isoformat()
    archivos_incluidos = 0

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        def get_person_folders(parent_folder):
            return [
                f"{parent_folder}/1. GENERALES/1. INE/",
                f"{parent_folder}/1. GENERALES/2. CONSTANCIA SITUACION FISCAL/",
                f"{parent_folder}/1. GENERALES/3. COMPROBANTE DOMICILIO/",
                f"{parent_folder}/1. GENERALES/4. ACTA NACIMIENTO/",
                f"{parent_folder}/1. GENERALES/5. ACTA MATRIMONIO/",
                f"{parent_folder}/1. GENERALES/PREVIOS/",
                f"{parent_folder}/2. ESTADOS DE CUENTA/",
                f"{parent_folder}/3. BURO DE CREDITO/",
                f"{parent_folder}/4. DECLARACIONES/",
            ]

        # 1. GENERAR ESTRUCTURA VACÍA BASE
        carpetas_base = get_person_folders(f"{empresa_nombre}/{rep_folder}")
        carpetas_base.extend([
            f"{empresa_nombre}/2. {empresa_nombre}/0. PRE ANALISIS/",
            f"{empresa_nombre}/2. {empresa_nombre}/1. ACTAS/ACTA CONSTITUTIVA/",
            f"{empresa_nombre}/2. {empresa_nombre}/1. ACTAS/ACTAS DE ASAMBLEA/",
            f"{empresa_nombre}/2. {empresa_nombre}/1. ACTAS/REGISTRO PUBLICO/",
            f"{empresa_nombre}/2. {empresa_nombre}/2. ESTADOS FINANCIEROS/",
            f"{empresa_nombre}/2. {empresa_nombre}/3. ESTADOS DE CUENTA/",
            f"{empresa_nombre}/2. {empresa_nombre}/4. BURO DE CREDITO/",
            f"{empresa_nombre}/2. {empresa_nombre}/5. DECLARACIONES/",
            f"{empresa_nombre}/2. {empresa_nombre}/6. GENERALES/1. CONSTANCIA SITUACION FISCAL/",
            f"{empresa_nombre}/2. {empresa_nombre}/6. GENERALES/2. COMPROBANTE DOMICILIO/",
            f"{empresa_nombre}/2. {empresa_nombre}/6. GENERALES/3. OPINION DE CUMPLIMIENTO/",
            f"{empresa_nombre}/2. {empresa_nombre}/6. GENERALES/4. FIEL/",
            f"{empresa_nombre}/2. {empresa_nombre}/6. GENERALES/PREVIOS/",
            f"{empresa_nombre}/2. {empresa_nombre}/7. OTROS/",
        ])
        
        # Add folders for each accionista dynamically
        for acc in acc_resp.data or []:
            acc_name = acc.get("nombre") or f"Accionista {acc['orden']}"
            idx = acc['orden'] + 1
            acc_folder = f"{empresa_nombre}/1.{idx} {acc_name.upper()}"
            carpetas_base.extend(get_person_folders(acc_folder))
            
        # Add folders for each sub empresa dynamically
        base_idx = len(acc_resp.data or []) + 2
        for i, sub in enumerate(sub_resp.data or []):
            sub_name = sub.get("nombre") or f"Sub Empresa {sub['orden']}"
            rol_text = "AVAL" if sub.get("rol") == "EMPRESA AVAL" else "GRUPO"
            sub_folder = f"{empresa_nombre}/1.{base_idx + i} {rol_text} - {sub_name.upper()}"
            carpetas_base.extend([
                f"{sub_folder}/0. PRE ANALISIS/",
                f"{sub_folder}/1. ACTAS/ACTA CONSTITUTIVA/",
                f"{sub_folder}/2. ESTADOS FINANCIEROS/",
                f"{sub_folder}/3. ESTADOS DE CUENTA/",
                f"{sub_folder}/4. BURO DE CREDITO/",
                f"{sub_folder}/5. DECLARACIONES/",
                f"{sub_folder}/6. GENERALES/1. CONSTANCIA SITUACION FISCAL/",
                f"{sub_folder}/6. GENERALES/2. COMPROBANTE DOMICILIO/",
                f"{sub_folder}/6. GENERALES/3. OPINION DE CUMPLIMIENTO/",
            ])
            
        # Crear carpetas de banco vacías
        for b_name in bancos_dict.values():
            carpetas_base.append(f"{empresa_nombre}/2. {empresa_nombre}/3. ESTADOS DE CUENTA/{b_name}/")
            
        for c in carpetas_base:
            zf.writestr(zipfile.ZipInfo(c), b'')

        rutas_agregadas = set()
        docs_a_bajar = []

        for doc in todos_docs:
            storage_path = doc.get("storage_path")
            if not storage_path:
                continue
                
            try:
                raw_name = doc.get("nombre_archivo", storage_path.split("/")[-1])
                tipo = doc.get("tipo_documento", "doc")
                is_rep = tipo in CLAVES_REPRESENTANTE
                
                person_name = None
                if is_rep:
                    person_name = "REPRESENTANTE LEGAL"
                elif tipo.endswith("_accionista"):
                    acc_id = doc.get("accionista_id")
                    acc_obj = next((a for a in (acc_resp.data or []) if a["id"] == acc_id), None)
                    person_name = acc_obj.get("nombre") if acc_obj else "ACCIONISTA"
                
                ine_name = doc.get("extracted_data", {}).get("nombre_extraido") if isinstance(doc.get("extracted_data"), dict) else None
                nombre_archivo = format_generales_filename(tipo, raw_name, is_rep, person_name, ine_name)
                
                # ==== LÓGICA DE MAPEO DE CARPETAS ====
                # Directorio Raíz: GRUPO
                ruta_base = f"{empresa_nombre}/"
                ruta_final = ""
                
                if tipo in CLAVES_REPRESENTANTE:
                    rep_folder_str = rep_folder # Use the one defined at the top
                    if tipo == "ine_representante":
                        ruta_final = f"{rep_folder_str}/1. GENERALES/1. INE/{nombre_archivo}"
                    elif tipo == "csf_representante":
                        ruta_final = f"{rep_folder_str}/1. GENERALES/2. CONSTANCIA SITUACION FISCAL/{nombre_archivo}"
                    elif tipo in ["comprobante_domicilio_representante", "cd_representante"]:
                        ruta_final = f"{rep_folder_str}/1. GENERALES/3. COMPROBANTE DOMICILIO/{nombre_archivo}"
                    elif tipo == "acta_nacimiento_representante":
                        ruta_final = f"{rep_folder_str}/1. GENERALES/4. ACTA NACIMIENTO/{nombre_archivo}"
                    elif tipo == "acta_matrimonio_representante" or tipo == "acta_matrimonio":
                        ruta_final = f"{rep_folder_str}/1. GENERALES/5. ACTA MATRIMONIO/{nombre_archivo}"
                    elif tipo in ["buro_representante", "buro_score_representante"]:
                        ruta_final = f"{rep_folder_str}/3. BURO DE CREDITO/{nombre_archivo}"
                    elif "declaracion" in tipo and "representante" in tipo:
                        ruta_final = f"{rep_folder_str}/4. DECLARACIONES/{nombre_archivo}"
                    else:
                        ruta_final = f"{rep_folder_str}/1. GENERALES/PREVIOS/{nombre_archivo}"
                elif tipo.endswith("_accionista"):
                    acc_id = doc.get("accionista_id")
                    acc_obj = next((a for a in (acc_resp.data or []) if a["id"] == acc_id), None)
                    if acc_obj:
                        acc_name = acc_obj.get("nombre") or f"Accionista {acc_obj['orden']}"
                        idx = acc_obj['orden'] + 1
                        acc_folder_str = f"1.{idx} {acc_name.upper()}"
                        
                        if tipo == "ine_accionista":
                            ruta_final = f"{acc_folder_str}/1. GENERALES/1. INE/{nombre_archivo}"
                        elif tipo == "csf_accionista":
                            ruta_final = f"{acc_folder_str}/1. GENERALES/2. CONSTANCIA SITUACION FISCAL/{nombre_archivo}"
                        elif tipo == "comprobante_domicilio_accionista":
                            ruta_final = f"{acc_folder_str}/1. GENERALES/3. COMPROBANTE DOMICILIO/{nombre_archivo}"
                        elif tipo == "buro_accionista" or tipo == "buro_score_accionista":
                            ruta_final = f"{acc_folder_str}/3. BURO DE CREDITO/{nombre_archivo}"
                        elif tipo == "acta_matrimonio_accionista":
                            ruta_final = f"{acc_folder_str}/1. GENERALES/5. ACTA MATRIMONIO/{nombre_archivo}"
                        else:
                            ruta_final = f"{acc_folder_str}/1. GENERALES/PREVIOS/{nombre_archivo}"
                
                elif tipo.endswith("_sub_empresa"):
                    sub_id = doc.get("sub_empresa_id")
                    sub_obj = next((s for s in (sub_resp.data or []) if s["id"] == sub_id), None)
                    if sub_obj:
                        sub_name = sub_obj.get("nombre") or f"Sub Empresa {sub_obj['orden']}"
                        rol_text = "AVAL" if sub_obj.get("rol") == "EMPRESA AVAL" else "GRUPO"
                        
                        base_idx = len(acc_resp.data or []) + 2
                        i = (sub_resp.data or []).index(sub_obj)
                        sub_folder_str = f"1.{base_idx + i} {rol_text} - {sub_name.upper()}"
                        
                        if tipo == "csf_sub_empresa":
                            ruta_final = f"{sub_folder_str}/6. GENERALES/1. CONSTANCIA SITUACION FISCAL/{nombre_archivo}"
                        elif tipo == "comprobante_domicilio_sub_empresa":
                            ruta_final = f"{sub_folder_str}/6. GENERALES/2. COMPROBANTE DOMICILIO/{nombre_archivo}"
                        elif tipo == "opinion_cumplimiento_sub_empresa":
                            ruta_final = f"{sub_folder_str}/6. GENERALES/3. OPINION DE CUMPLIMIENTO/{nombre_archivo}"
                        elif tipo == "buro_sub_empresa":
                            ruta_final = f"{sub_folder_str}/4. BURO DE CREDITO/{nombre_archivo}"
                        elif tipo == "acta_constitutiva_sub_empresa":
                            ruta_final = f"{sub_folder_str}/1. ACTAS/ACTA CONSTITUTIVA/{nombre_archivo}"
                        elif tipo == "estados_financieros_sub_empresa":
                            ruta_final = f"{sub_folder_str}/2. ESTADOS FINANCIEROS/{nombre_archivo}"
                        elif tipo == "declaraciones_sub_empresa":
                            ruta_final = f"{sub_folder_str}/5. DECLARACIONES/{nombre_archivo}"
                        elif tipo == "estados_cuenta_sub_empresa":
                            ruta_final = f"{sub_folder_str}/3. ESTADOS DE CUENTA/{nombre_archivo}"
                        elif tipo == "curriculum_sub_empresa":
                            ruta_final = f"{sub_folder_str}/0. PRE ANALISIS/{nombre_archivo}"
                        else:
                            ruta_final = f"{sub_folder_str}/0. PRE ANALISIS/{nombre_archivo}"
                else:
                    emp_folder = f"2. {empresa_nombre}"
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
            is_rep = tipo in CLAVES_REPRESENTANTE
            ine_name = doc.get("extracted_data", {}).get("nombre_extraido") if isinstance(doc.get("extracted_data"), dict) else None
            nombre_archivo = format_generales_filename(tipo, nombre_archivo, is_rep, ine_name=ine_name)
            
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
async def descargar_documento_individual(empresa_id: str, doc_id: str, is_rep: bool = False, preview: bool = False):
    """
    Descarga un archivo individual, marcándolo como descargado.
    """
    sb = get_supabase_admin()
    table = "documentos_representante" if is_rep else "documentos_expediente"
    
    doc_resp = sb.table(table).select("*").eq("id", doc_id).execute()
    doc = doc_resp.data[0] if doc_resp.data else None
    
    if not doc:
        # Fallback to accionistas
        table = "documentos_accionista"
        doc_resp = sb.table(table).select("*").eq("id", doc_id).execute()
        doc = doc_resp.data[0] if doc_resp.data else None
        
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    storage_path = doc.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=400, detail="El documento no tiene un archivo asociado")
        
    raw_name = doc.get("nombre_archivo", storage_path.split("/")[-1])
    tipo = doc.get("tipo_documento", "doc")
    is_rep = tipo in CLAVES_REPRESENTANTE
    
    person_name = None
    if is_rep:
        person_name = "REPRESENTANTE LEGAL"
    elif table == "documentos_accionista":
        # Fetch accionista name
        acc_id = doc.get("accionista_id")
        if acc_id:
            acc_resp = sb.table("accionistas").select("nombre").eq("id", acc_id).single().execute()
            if acc_resp.data:
                person_name = acc_resp.data.get("nombre")
        if not person_name:
            person_name = "ACCIONISTA"
            
    nombre_archivo = format_generales_filename(tipo, raw_name, is_rep, person_name)
    
    try:
        options = {} if preview else {"download": nombre_archivo}
        exp_time = 3600 if preview else 60
        res = sb.storage.from_("expedientes_clientes").create_signed_url(
            storage_path, 
            expires_in=exp_time, 
            options=options
        )
        signed_url = res.get("signedURL") or res.get("signedUrl")
        if not signed_url:
            raise ValueError("No se obtuvo URL firmada")
    except Exception as e:
        logger.error(f"Error generando URL firmada para {storage_path}: {e}")
        raise HTTPException(status_code=500, detail="Error descargando de Storage")
        
    ahora = datetime.now(timezone.utc).isoformat()
    sb.table(table).update({
        "descargado": True,
        "descargado_en": ahora,
    }).eq("id", doc_id).execute()
    
    return {"url": signed_url, "filename": nombre_archivo}


@router.get("/empresas/{empresa_id}/buro-mops")
async def get_buro_mops(empresa_id: str, tipo_buro: str = "buro_credito", refresh: bool = False):
    """
    Descarga el PDF de Buró de Crédito de la empresa (o representante) y extrae el análisis de MOPs
    (Manera de Pago / Histórico de Pagos).

    Returns:
        - mops_detectados: bool — si hay MOPs nivel 2+
        - alerta: bool — si hay MOPs nivel 3+ (requieren atención)
        - años: lista de años encontrados en el reporte (desc)
        - niveles: dict nivel -> {año -> conteo}
        - mops_alerta: lista de {nivel, año, conteo} para niveles 3+
        - total_mops_nivel2_plus: total de ocurrencias nivel 2+
    """
    sb = get_supabase_admin()

    # Verificar que la empresa existe
    emp_resp = sb.table("empresas").select("nombre").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    table = "documentos_representante" if tipo_buro == "buro_representante" else "documentos_expediente"

    # Buscar el documento de Buró de Crédito
    doc_resp = (
        sb.table(table)
        .select("id, storage_path, nombre_archivo, estado, extracted_data")
        .eq("empresa_id", empresa_id)
        .eq("tipo_documento", tipo_buro)
        .execute()
    )

    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="No se encontró el documento de Buró de Crédito para esta empresa")

    doc = doc_resp.data[0]
    storage_path = doc.get("storage_path")

    if not storage_path:
        raise HTTPException(status_code=400, detail="El Buró de Crédito aún no tiene un archivo subido")

    # Extraer MOPs (de base de datos o procesar y guardar)
    # Solo usar caché si: tenemos datos, no es refresh, y cuentas NO está vacío
    cached = doc.get("extracted_data")
    has_valid_cache = (
        cached
        and "cuentas" in cached
        and len(cached.get("cuentas", [])) > 0
        and not refresh
    )
    if has_valid_cache:
        resultado = doc["extracted_data"]
    else:
        resultado = extraer_mops_desde_storage(storage_path, sb)
        # Guardar para la próxima vez
        try:
            sb.table(table).update({"extracted_data": resultado}).eq("id", doc["id"]).execute()
        except Exception as e:
            pass # ignore if it fails
            
    resultado["empresa_id"] = empresa_id
    resultado["documento_id"] = doc.get("id")
    resultado["nombre_archivo"] = doc.get("nombre_archivo")
    resultado["estado_documento"] = doc.get("estado")

    return resultado

from app.Buro_Credito.score_extractor import extraer_score_desde_storage

@router.get("/empresas/{empresa_id}/buro-score")
async def get_buro_score(empresa_id: str, tipo_buro: str = "buro_score_representante", refresh: bool = False):
    """
    Descarga el PDF de Buró de Crédito Mi Score y extrae el puntaje.
    """
    sb = get_supabase_admin()

    emp_resp = sb.table("empresas").select("nombre").eq("id", empresa_id).single().execute()
    if not emp_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    table = "documentos_representante" if "representante" in tipo_buro else "documentos_expediente"

    doc_resp = (
        sb.table(table)
        .select("id, storage_path, nombre_archivo, estado, extracted_data")
        .eq("empresa_id", empresa_id)
        .eq("tipo_documento", tipo_buro)
        .single()
        .execute()
    )

    if not doc_resp.data:
        raise HTTPException(status_code=404, detail="No se encontró el documento Mi Score")

    doc = doc_resp.data
    storage_path = doc.get("storage_path")

    if not storage_path:
        raise HTTPException(status_code=400, detail="El Mi Score aún no tiene archivo")

    if doc.get("extracted_data") and not refresh:
        resultado = doc["extracted_data"]
    else:
        resultado = extraer_score_desde_storage(storage_path, sb)
        try:
            sb.table(table).update({"extracted_data": resultado}).eq("id", doc["id"]).execute()
        except Exception:
            pass

    resultado["empresa_id"] = empresa_id
    resultado["documento_id"] = doc.get("id")
    
    return resultado

from app.config import UPLOAD_DIR
from app.pdf_extractor import extract_text
from app.bank_detector import detect_bank
import uuid
import os
from datetime import datetime

@router.post("/empresas/{empresa_id}/export-to-teaser")
async def export_to_teaser(empresa_id: str):
    """
    Descarga los estados de cuenta de la empresa desde Supabase
    y los carga directamente en la memoria local de AutoTeaser.
    """
    sb = get_supabase_admin()
    
    # 1. Obtener documentos de expedientes para la empresa que sean estados de cuenta válidos
    docs_resp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).in_("estado", ["PENDIENTE", "APROBADO"]).execute()
    if not docs_resp.data:
        raise HTTPException(status_code=404, detail="No hay documentos para exportar")
        
    bank_docs = [d for d in docs_resp.data if d.get("cuenta_bancaria_id")]
    if not bank_docs:
        raise HTTPException(status_code=404, detail="No hay estados de cuenta para exportar")

    # 2. Limpiar documentos actuales de AutoTeaser para no mezclarlos
    import app.main
    app.main.documents.clear()
    
    count = 0
    # 3. Descargar y procesar cada documento
    for doc in bank_docs:
        storage_path = doc.get("storage_path")
        if not storage_path: continue
        
        try:
            file_bytes = sb.storage.from_("expedientes_clientes").download(storage_path)
            doc_id = str(uuid.uuid4())[:8]
            safe_name = f"{doc_id}_{doc['nombre_archivo']}"
            file_path = UPLOAD_DIR / safe_name
            
            with open(file_path, "wb") as f:
                f.write(file_bytes)
                
            extraction = extract_text(file_path)
            detected_bank = detect_bank(pdf_path=file_path, text=extraction["full_text"]) or doc.get("nombre_carpeta")
            
            app.main.documents[doc_id] = {
                "id": doc_id,
                "file_name": doc["nombre_archivo"],
                "file_path": str(file_path),
                "uploaded_at": datetime.now().isoformat(),
                "extraction": extraction,
                "detected_bank": detected_bank,
                "status": "uploaded",
                "parsed_data": None,
                "output_file": None,
            }
            count += 1
        except Exception as e:
            print(f"Error procesando {doc['nombre_archivo']} para exportación: {e}")
            continue
            
    return {"success": True, "count": count}

def background_sync_all_to_drive(empresa_id: str, empresa_nombre: str, estructura: dict, service, rep_name: str = None):
    import re
    sb = get_supabase_admin()
    docs1 = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).execute()
    docs2 = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).execute()
    docs3 = sb.table("documentos_accionista").select("*").eq("empresa_id", empresa_id).execute()
    all_docs = (docs1.data or []) + (docs2.data or []) + (docs3.data or [])
    
    from app.drive_service import upload_file_to_drive, get_ec_subfolder
    
    for doc in all_docs:
        if not doc.get("storage_path") or doc.get("estado") in ["FALTANTE", "RECHAZADO"]:
            continue
            
        try:
            res = sb.storage.from_("expedientes_clientes").download(doc["storage_path"])
            
            tipo_documento = doc["tipo_documento"]
            raw_name = doc["nombre_archivo"] or ""

            is_rep = "representante" in tipo_documento or doc.get("_tabla") == "representante"
            
            person_name = None
            if is_rep:
                person_name = rep_name.upper() if rep_name else "REPRESENTANTE LEGAL"
            elif tipo_documento.endswith("_accionista"):
                acc_id = doc.get("accionista_id")
                # We need the name of the accionista, but we don't have it easily here without a query or passing it
                # However we can query it quickly or just pass "ACCIONISTA" if we are in background task.
                if acc_id:
                    acc_resp = sb.table("accionistas").select("nombre").eq("id", acc_id).single().execute()
                    if acc_resp.data:
                        person_name = acc_resp.data.get("nombre")
                if not person_name:
                    person_name = "ACCIONISTA"
                    
            nombre_archivo = format_generales_filename(tipo_documento, raw_name, is_rep, person_name)

            from app.drive_service import find_or_create_folder
            if is_rep or tipo_documento.endswith("_accionista"):
                if is_rep:
                    base_parent_id = estructura["representante"]
                else:
                    acc_id = doc.get("accionista_id")
                    base_parent_id = estructura.get("accionistas", {}).get(acc_id, estructura["root"]["id"])
                
                if "ine" in tipo_documento:
                    g_id = find_or_create_folder(service, "1. GENERALES", base_parent_id)["id"]
                    folder_id = find_or_create_folder(service, "1. INE", g_id)["id"]
                elif "csf" in tipo_documento:
                    g_id = find_or_create_folder(service, "1. GENERALES", base_parent_id)["id"]
                    folder_id = find_or_create_folder(service, "2. CONSTANCIA SITUACION FISCAL", g_id)["id"]
                elif "comprobante" in tipo_documento or "cd_" in tipo_documento:
                    g_id = find_or_create_folder(service, "1. GENERALES", base_parent_id)["id"]
                    folder_id = find_or_create_folder(service, "3. COMPROBANTE DOMICILIO", g_id)["id"]
                elif "acta_nacimiento" in tipo_documento:
                    g_id = find_or_create_folder(service, "1. GENERALES", base_parent_id)["id"]
                    folder_id = find_or_create_folder(service, "4. ACTA NACIMIENTO", g_id)["id"]
                elif "acta_matrimonio" in tipo_documento:
                    g_id = find_or_create_folder(service, "1. GENERALES", base_parent_id)["id"]
                    folder_id = find_or_create_folder(service, "5. ACTA MATRIMONIO", g_id)["id"]
                elif "buro" in tipo_documento:
                    folder_id = find_or_create_folder(service, "3. BURO DE CREDITO", base_parent_id)["id"]
                elif "declaracion" in tipo_documento:
                    folder_id = find_or_create_folder(service, "4. DECLARACIONES", base_parent_id)["id"]
                else:
                    g_id = find_or_create_folder(service, "1. GENERALES", base_parent_id)["id"]
                    folder_id = find_or_create_folder(service, "PREVIOS", g_id)["id"]
            else:
                if tipo_documento.startswith("ec_") or "estado_cuenta" in tipo_documento:
                    # 3. ESTADOS DE CUENTA > [BANCO - CUENTA (BANCO XXXX)] > [AAAA]
                    year_match = re.match(r'^(\d{4})\.', nombre_archivo)
                    year = year_match.group(1) if year_match else "Sin Año"
                    # nombre_carpeta field holds the bank folder name (e.g. "Banorte - CUENTA (BANORTE 4215)")
                    banco_nombre = doc.get("nombre_carpeta") or "Desconocido"
                    folder_id = get_ec_subfolder(service, estructura, banco_nombre, year)
                elif "buro" in tipo_documento:
                    folder_id = estructura["buro_credito"]
                elif "declaracion" in tipo_documento or "csf" in tipo_documento or "opinion" in tipo_documento:
                    folder_id = estructura["declaraciones"]
                elif "acta" in tipo_documento or "poder" in tipo_documento:
                    folder_id = estructura["legal"]
                elif "eeff" in tipo_documento or "estados_financieros" in tipo_documento:
                    folder_id = estructura["financieros"]
                else:
                    folder_id = estructura["vigentes"]
                
            content_type = "application/pdf"
            if nombre_archivo.endswith(".xml"): content_type = "application/xml"
            if nombre_archivo.endswith(".zip"): content_type = "application/zip"
            
            upload_file_to_drive(service, res, nombre_archivo, content_type, folder_id)
        except Exception as e:
            logger.error(f"Error syncing doc {doc.get('nombre_archivo')} to Drive: {e}")

@router.post("/empresas/{empresa_id}/drive/init")
async def init_drive(empresa_id: str):
    from app.drive_service import get_drive_service, get_shared_parent_folder, create_empresa_structure
    sb = get_supabase_admin()
    empresa_resp = sb.table("empresas").select("nombre, representante_legal").eq("id", empresa_id).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    
    empresa_nombre = empresa_resp.data["nombre"]
    rep_name = empresa_resp.data.get("representante_legal")
    try:
        service = get_drive_service()
        parent_id = get_shared_parent_folder(service)
        
        # Fetch accionistas
        acc_resp = sb.table("accionistas").select("*").eq("empresa_id", empresa_id).execute()
        accionistas = acc_resp.data or []
        
        estructura = create_empresa_structure(service, empresa_nombre, parent_id, accionistas, rep_name=rep_name)
        
        root_folder_id = estructura["root"]["id"]
        return {"success": True, "message": "Carpeta generada correctamente.", "link": f"https://drive.google.com/drive/folders/{root_folder_id}"}
    except Exception as e:
        logger.error(f"Error init Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/empresas/{empresa_id}/drive/sync")
async def sync_drive(empresa_id: str, background_tasks: BackgroundTasks):
    from app.drive_service import get_drive_service, get_shared_parent_folder, create_empresa_structure
    sb = get_supabase_admin()
    empresa_resp = sb.table("empresas").select("nombre, representante_legal").eq("id", empresa_id).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    
    empresa_nombre = empresa_resp.data["nombre"]
    rep_name = empresa_resp.data.get("representante_legal")
    try:
        service = get_drive_service()
        parent_id = get_shared_parent_folder(service)
        
        # Fetch accionistas
        acc_resp = sb.table("accionistas").select("*").eq("empresa_id", empresa_id).execute()
        accionistas = acc_resp.data or []
        
        estructura = create_empresa_structure(service, empresa_nombre, parent_id, accionistas, rep_name=rep_name)
        
        background_tasks.add_task(background_sync_all_to_drive, empresa_id, empresa_nombre, estructura, service, rep_name)
        
        root_folder_id = estructura["root"]["id"]
        return {"success": True, "message": "Sincronización iniciada en segundo plano. La carpeta puede tardar unos minutos en reflejar los archivos.", "link": f"https://drive.google.com/drive/folders/{root_folder_id}"}
    except Exception as e:
        logger.error(f"Error sync Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

