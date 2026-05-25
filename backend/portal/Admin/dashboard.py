"""
dashboard.py — Panel de control del equipo Admin.

Endpoint:
- GET /api/portal/admin/pendientes
  Devuelve todos los documentos en estado PENDIENTE agrupados por empresa.
- GET /api/portal/admin/empresas
  Lista todas las empresas con el resumen de su expediente.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from portal.shared.supabase_db import get_supabase_admin
from portal.Cliente.expedientes import get_todos_los_documentos_requeridos

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
    documentos_requeridos = get_todos_los_documentos_requeridos()
    
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
            })
            
    # Also include any documents uploaded that might not be in the current required list 
    # (e.g. if required list changed but they had old uploads)
    req_claves = {d["clave"] for d in documentos_requeridos}
    for doc_subido in docs_subidos:
        if doc_subido["tipo_documento"] not in req_claves:
            doc_subido["empresa_nombre"] = empresa_info.get("nombre")
            doc_subido["empresa_rfc"] = empresa_info.get("rfc")
            doc_subido["nombre_esperado"] = doc_subido["tipo_documento"]
            doc_subido["grupo"] = "empresa" # default
            documentos_completos.append(doc_subido)
        
    return {
        "empresa": empresa_info,
        "documentos": documentos_completos,
        "total": len(documentos_completos)
    }
