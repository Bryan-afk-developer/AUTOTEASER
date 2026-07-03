"""
expedientes.py — Consulta del expediente del cliente.

Calcula dinámicamente qué documentos se requieren y devuelve su estado actual.
Categorías:
  - Legal (Actas constitutiva y asambleas)
  - Estados de Cuenta (últimos 7 meses, desde 2 meses antes del actual)
  - Financieros (Balance, Resultados, Analíticas, Firmado × 4 periodos)
  - Declaraciones SAT (Acuse + Excel × 3 años fiscales cerrados)
  - Vigentes (Buró, CSF, Comprobante, Opinión, Currículum)
  - Representante Legal (INE, CSF, Acta Matrimonio, Comprobante Domicilio)

Endpoint:
- GET /api/portal/cliente/expediente
"""
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException, Header

from pydantic import BaseModel
from portal.Cliente.auth import get_user_from_token
from portal.shared.supabase_db import get_supabase_admin
import json
import google.generativeai as genai
from app.config import GEMINI_API_KEY
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

BUCKET_NAME = "expedientes_clientes"
router = APIRouter()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN ESTÁTICA DE DOCUMENTOS
# ══════════════════════════════════════════════════════════════════════════════

# 1. Documentos Legales
DOCUMENTOS_LEGALES = []

# 5. Documentos Vigentes (validez temporal)
DOCUMENTOS_VIGENTES = [
    {
        "clave": "buro_credito",
        "nombre": "Buró de Crédito",
        "descripcion": "Reporte de Buró de Crédito actualizado (vigente al mes actual)",
        "categoria": "fiscal",
        "icono": "📊",
        "grupo": "vigentes",
    },
    {
        "clave": "buro_score_empresa",
        "nombre": "Buró de Crédito Mi Score",
        "descripcion": "Reporte de Mi Score de la Empresa",
        "categoria": "financiero",
        "icono": "📈",
        "grupo": "vigentes",
    },
    {
        "clave": "csf_empresa",
        "nombre": "Constancia de Situación Fiscal",
        "descripcion": "Emitida por el SAT, correspondiente al mes actual",
        "categoria": "fiscal",
        "icono": "🏛️",
        "grupo": "vigentes",
    },
    {
        "clave": "comprobante_domicilio_empresa",
        "nombre": "Comprobante de Domicilio",
        "descripcion": "No mayor a 3 meses, de preferencia recibo de luz",
        "categoria": "legal",
        "icono": "🏠",
        "grupo": "vigentes",
    },
    {
        "clave": "opinion_cumplimiento",
        "nombre": "Opinión de Cumplimiento",
        "descripcion": "Emitida por el SAT, correspondiente al mes actual",
        "categoria": "fiscal",
        "icono": "",
        "grupo": "vigentes",
    },
    {
        "clave": "curriculum_empresa",
        "nombre": "Currículum de la Empresa",
        "descripcion": "Presentación de la empresa o grupo empresarial",
        "categoria": "corporativo",
        "icono": "📋",
        "grupo": "vigentes",
    },
]

# 6. Documentos del Representante Legal
DOCUMENTOS_REPRESENTANTE = [
    {
        "clave": "ine_representante",
        "nombre": "INE o Identificación (Representante)",
        "descripcion": "Identificación oficial vigente (ambos lados)",
        "categoria": "legal",
        "icono": "🪪",
        "grupo": "representante",
    },
    {
        "clave": "csf_representante",
        "nombre": "Constancia de Situación Fiscal (Representante)",
        "descripcion": "Emitida por el SAT, vigente",
        "categoria": "fiscal",
        "icono": "🏛️",
        "grupo": "representante",
    },
    {
        "clave": "acta_matrimonio",
        "nombre": "Acta de Matrimonio",
        "descripcion": "En caso de aplicar",
        "categoria": "legal",
        "icono": "💍",
        "grupo": "representante",
    },
    {
        "clave": "comprobante_domicilio_representante",
        "nombre": "Comprobante de Domicilio (Representante)",
        "descripcion": "No mayor a 3 meses, de preferencia recibo de luz",
        "categoria": "legal",
        "icono": "🏠",
        "grupo": "representante",
    },
    {
        "clave": "buro_representante",
        "nombre": "Buró de Crédito (Representante)",
        "descripcion": "Reporte de Crédito Especial",
        "categoria": "financiero",
        "icono": "📊",
        "grupo": "representante",
    },
    {
        "clave": "buro_score_representante",
        "nombre": "Buró de Crédito (Mi Score)",
        "descripcion": "Reporte de Mi Score de Buró de Crédito",
        "categoria": "financiero",
        "icono": "🎯",
        "grupo": "representante",
    },
]

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ══════════════════════════════════════════════════════════════════════════════
# GENERADORES DINÁMICOS
# ══════════════════════════════════════════════════════════════════════════════

def calcular_estados_de_cuenta(banco: dict = None) -> list[dict]:
    """
    Genera 7 slots genéricos para estados de cuenta de la cuenta bancaria.
    """
    docs = []
    
    # Si no hay banco, no devolvemos slots genéricos
    if not banco:
        return docs
        
    nombre_banco = banco["nombre_banco"]
    cuenta_id = banco["id"]
    
    for i in range(1, 8):
        clave = f"ec_{cuenta_id}_{i}"
        docs.append({
            "clave": clave,
            "nombre": f"Estado de Cuenta {i}",
            "descripcion": f"Documento de estado de cuenta #{i}",
            "categoria": "bancario",
            "icono": "🏦",
            "grupo": "estados_cuenta",
            "cuenta_bancaria_id": cuenta_id,
            "nombre_carpeta": nombre_banco,
            "orden": i
        })
    return docs


def calcular_financieros() -> list[dict]:
    """
    Genera los documentos de estados financieros requeridos.

    Los estados financieros se entregan como UN SOLO ARCHIVO por periodo
    que incluye: Balance General, Estado de Resultados, Analíticas y Firmado.

    Periodos:
      - Parcial al mes de 2 meses antes del actual (año en curso)
      - 3 años fiscales completos anteriores

    Ej: Mayo 2026 → Parcial Marzo 2026 + 2025 + 2024 + 2023
    """
    hoy = date.today()
    mes_parcial = hoy - relativedelta(months=2)
    año_actual = hoy.year

    # Periodo parcial del año en curso
    periodos = [
        {
            "sufijo": mes_parcial.strftime("%Y_%m"),
            "label": f"Parcial {MESES_ES[mes_parcial.month]} {mes_parcial.year}",
            "desc": f"Parciales al mes de {MESES_ES[mes_parcial.month]} {mes_parcial.year}",
        },
    ]
    # 3 años fiscales completos anteriores
    for i in range(1, 4):
        año = año_actual - i
        periodos.append({
            "sufijo": str(año),
            "label": f"Ejercicio Fiscal {año}",
            "desc": f"Ejercicio fiscal completo {año}",
        })

    docs = []
    for periodo in periodos:
        clave = f"financiero_eeff_{periodo['sufijo']}"
        docs.append({
            "clave": clave,
            "nombre": f"Estados Financieros – {periodo['label']}",
            "descripcion": (
                f"Un solo archivo que incluya: Balance General, Estado de Resultados, "
                f"Analíticas y Firmado · {periodo['desc']}"
            ),
            "categoria": "financiero",
            "icono": "📊",
            "grupo": "financieros",
        })

    return docs


def calcular_declaraciones() -> list[dict]:
    """
    Genera los documentos de declaraciones fiscales anuales.
    
    Regla: las declaraciones anuales salen el 31 de marzo.
      - Si ya pasó marzo → incluye el año inmediato anterior
      - Si no ha pasado marzo → empieza desde 2 años atrás
      - Siempre 3 años fiscales
    
    Cada año requiere 2 documentos:
      - Declaración Anual con Acuse (PDF del SAT)
      - Declaración Anual del Ejercicio (PDF del SAT)
    
    Las claves coinciden con lo que detecta Detect_Sat_file.py:
      declaracion_acuse_{year}       → ACUSE DE RECIBO
      declaracion_declaracion_{year} → DECLARACIÓN DEL EJERCICIO

    Ej: Mayo 2026 (pasó marzo) → 2025, 2024, 2023
    Ej: Feb 2026 (no ha pasado marzo) → 2024, 2023, 2022
    """
    hoy = date.today()

    if hoy.month >= 4:
        año_mas_reciente = hoy.year - 1
    else:
        año_mas_reciente = hoy.year - 2

    tipos = [
        ("acuse",       "Acuse de Recibo",        "📋",
         "Acuse de recibo emitido por el SAT al presentar la declaración anual"),
        ("declaracion", "Declaración del Ejercicio", "📄",
         "PDF de la declaración anual ISR descargado del portal del SAT"),
    ]

    docs = []
    for i in range(3):
        año = año_mas_reciente - i
        for tipo_clave, tipo_nombre, tipo_icono, tipo_desc in tipos:
            clave = f"declaracion_{tipo_clave}_{año}"
            docs.append({
                "clave": clave,
                "nombre": f"{tipo_nombre} – {año}",
                "descripcion": f"{tipo_desc} · Ejercicio fiscal {año}",
                "categoria": "fiscal",
                "icono": tipo_icono,
                "grupo": "declaraciones",
                "año": año,
                "tipo_declaracion": tipo_clave,
            })

    return docs


def calcular_actas(docs_subidos: dict = None) -> list[dict]:
    docs_subidos = docs_subidos or {}
    actas_subidas = [d for d in docs_subidos.values() if d["tipo_documento"].startswith("acta_constitutiva")]
    
    docs = []
    if not actas_subidas:
        docs.append({
            "clave": "acta_constitutiva",
            "nombre": "Acta Constitutiva y Asambleas Posteriores",
            "descripcion": "Acta constitutiva y asambleas posteriores con inscripción en el RPC",
            "categoria": "legal",
            "icono": "📜",
            "grupo": "legal",
        })
    else:
        actas_subidas = sorted(actas_subidas, key=lambda x: x.get("subido_en") or "")
        for i, acta in enumerate(actas_subidas):
            docs.append({
                "clave": acta["tipo_documento"],
                "nombre": f"Acta Constitutiva / Asamblea ({i+1})",
                "descripcion": "Acta constitutiva o de asamblea",
                "categoria": "legal",
                "icono": "📜",
                "grupo": "legal",
            })
    return docs


# ══════════════════════════════════════════════════════════════════════════════
# COMBINADOR
# ══════════════════════════════════════════════════════════════════════════════

def get_todos_los_documentos_requeridos(bancos: list[dict] = None, docs_subidos: dict = None) -> list[dict]:
    """Combina todos los grupos de documentos en el orden de presentación.
    Las declaraciones SAT se calculan aparte (lista dinámica de lo subido).
    """
    docs_bancos = []
    if bancos:
        for banco in bancos:
            docs_bancos.extend(calcular_estados_de_cuenta(banco))

    return (
        DOCUMENTOS_LEGALES
        + calcular_actas(docs_subidos)
        + docs_bancos
        + calcular_financieros()
        + DOCUMENTOS_VIGENTES
        + DOCUMENTOS_REPRESENTANTE
    )


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/expediente")
async def get_expediente(authorization: str = Header(None)):
    """
    Devuelve el expediente completo del cliente.
    """
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    # Obtener empresa del usuario
    empresa_resp = (
        sb.table("empresas")
        .select("id, nombre")
        .eq("user_id", user_info["user_id"])
        .single()
        .execute()
    )
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa = empresa_resp.data
    empresa_id = empresa["id"]

    # Obtener bancos
    bancos_resp = sb.table("cuentas_bancarias").select("*").eq("empresa_id", empresa_id).execute()
    bancos = bancos_resp.data or []

    # Obtener documentos ya subidos de la BD (de ambas tablas)
    docs_resp = (
        sb.table("documentos_expediente")
        .select("*")
        .eq("empresa_id", empresa_id)
        .execute()
    )
    docs_empresa = docs_resp.data or []

    # Obtener documentos del representante
    rep_resp = (
        sb.table("documentos_representante")
        .select("*")
        .eq("empresa_id", empresa_id)
        .execute()
    )
    docs_representante = rep_resp.data or []

    # Combinar todos los documentos subidos
    todos_subidos = docs_empresa + docs_representante
    docs_subidos = {d["tipo_documento"]: d for d in todos_subidos}

    # Construir respuesta combinando requeridos con los subidos
    documentos_requeridos = get_todos_los_documentos_requeridos(bancos, docs_subidos)
    # --- Generación en lote de URLs firmadas para mayor velocidad ---
    paths_to_sign = [d["storage_path"] for d in todos_subidos if d.get("storage_path")]
    signed_urls_map = {}
    if paths_to_sign:
        try:
            signed_urls_resp = sb.storage.from_(BUCKET_NAME).create_signed_urls(paths_to_sign, 3600)
            for item in signed_urls_resp:
                if not item.get("error") and item.get("signedURL"):
                    signed_urls_map[item["path"]] = item["signedURL"]
        except Exception as e:
            logger.error(f"Error al generar URLs firmadas en lote: {e}")

    resultado = []
    aprobados = 0

    for doc_req in documentos_requeridos:
        clave = doc_req["clave"]
        doc_subido = docs_subidos.get(clave)

        if doc_subido:
            estado = doc_subido["estado"]
            url_documento = None
            storage_path = doc_subido.get("storage_path")
            if storage_path:
                url_documento = signed_urls_map.get(storage_path)

            entry = {
                **doc_req,
                "estado": estado,
                "documento_id": doc_subido["id"],
                "nombre_archivo": doc_subido.get("nombre_archivo"),
                "subido_en": doc_subido.get("subido_en"),
                "revisado_en": doc_subido.get("revisado_en"),
                "comentario_admin": doc_subido.get("comentario_admin"),
                "storage_path": storage_path,
                "url_documento": url_documento,
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
                "url_documento": None,
            }

        resultado.append(entry)

    # Agregar documentos "Otros" que no están en la lista de requeridos
    req_claves = {d["clave"] for d in documentos_requeridos}
    for doc_subido in todos_subidos:
        # Skip declaraciones (handled separately) and skip estados_cuenta slots not required
        tipo = doc_subido["tipo_documento"]
        if tipo.startswith("declaracion_"):
            continue
        if tipo not in req_claves and tipo.startswith("otros_"):
            estado = doc_subido["estado"]
            url_documento = None
            storage_path = doc_subido.get("storage_path")
            if storage_path:
                url_documento = signed_urls_map.get(storage_path)

            entry = {
                "clave": tipo,
                "nombre": doc_subido.get("nombre_archivo", "Otro Documento"),
                "descripcion": "Documento adicional subido por el cliente",
                "categoria": "otros",
                "icono": "📁",
                "grupo": "otros",
                "estado": estado,
                "documento_id": doc_subido["id"],
                "nombre_archivo": doc_subido.get("nombre_archivo"),
                "subido_en": doc_subido.get("subido_en"),
                "revisado_en": doc_subido.get("revisado_en"),
                "comentario_admin": doc_subido.get("comentario_admin"),
                "storage_path": storage_path,
                "url_documento": url_documento,
            }
            if estado == "APROBADO":
                aprobados += 1
            resultado.append(entry)

    # ── Declaraciones SAT — lista dinámica de lo que realmente subió el cliente ──
    from datetime import date as _date
    hoy_d = _date.today()
    año_min_requerido = 2023  # desde 2023 en adelante se pide al menos 2 archivos
    año_mas_reciente = hoy_d.year - 1 if hoy_d.month >= 4 else hoy_d.year - 2

    declaraciones_sat = []
    for doc_subido in docs_empresa:
        tipo = doc_subido["tipo_documento"]
        if not tipo.startswith("declaracion_"):
            continue
        storage_path = doc_subido.get("storage_path")
        url_documento = signed_urls_map.get(storage_path) if storage_path else None

        # Parse tipo: declaracion_{subtipo}_{year}_{uid} or declaracion_sinclasificar_{uuid}
        parts = tipo.split("_")  # ['declaracion', subtipo_or_sin, year, uid] or ['declaracion', 'sinclasificar', uid]
        subtipo = parts[1] if len(parts) > 1 else None
        year_str = parts[2] if (len(parts) > 2 and subtipo != "sinclasificar") else None

        if subtipo == "sinclasificar":
            label = "Sin clasificar"
            icono = "📁"
            año_val = None
            clasificado = False
        elif subtipo == "acuse" and year_str and year_str.isdigit():
            label = f"Acuse de Recibo – {year_str}"
            icono = "📋"
            año_val = int(year_str)
            clasificado = True
        elif subtipo == "acusecomp" and year_str and year_str.isdigit():
            label = f"Acuse de Recibo (Complementaria) – {year_str}"
            icono = "📋"
            año_val = int(year_str)
            clasificado = True
        elif subtipo == "declaracion" and year_str and year_str.isdigit():
            label = f"Declaración del Ejercicio – {year_str}"
            icono = "📄"
            año_val = int(year_str)
            clasificado = True
        elif subtipo == "declaracioncomp" and year_str and year_str.isdigit():
            label = f"Declaración del Ejercicio (Complementaria) – {year_str}"
            icono = "📄"
            año_val = int(year_str)
            clasificado = True
        else:
            label = doc_subido.get("nombre_archivo", tipo)
            icono = "📁"
            año_val = None
            clasificado = False

        declaraciones_sat.append({
            "clave": tipo,
            "nombre": label,
            "icono": icono,
            "año": año_val,
            "clasificado": clasificado,
            "estado": doc_subido["estado"],
            "documento_id": doc_subido["id"],
            "nombre_archivo": doc_subido.get("nombre_archivo"),
            "subido_en": doc_subido.get("subido_en"),
            "revisado_en": doc_subido.get("revisado_en"),
            "comentario_admin": doc_subido.get("comentario_admin"),
            "storage_path": storage_path,
            "url_documento": url_documento,
        })

    # Sort: clasificados primero (por año desc), sin clasificar al final
    declaraciones_sat.sort(key=lambda d: (
        0 if d["clasificado"] else 1,
        -(d["año"] or 0),
    ))

    # Evaluate completeness: need >= 2 files from año_min_requerido onwards
    archivos_validos = [
        d for d in declaraciones_sat
        if d["año"] is not None and d["año"] >= año_min_requerido
    ]
    declaraciones_completo = len(archivos_validos) >= 2

    total = len(resultado)
    progreso = round((aprobados / total) * 100) if total > 0 else 0

    # 5. Fetch Acta Principal Summary from Storage
    acta_principal_data = None
    try:
        files = sb.storage.from_(BUCKET_NAME).list(f"{empresa_id}")
        if files and any(f.get("name") == "acta_principal_summary.json" for f in files):
            summary_bytes = sb.storage.from_(BUCKET_NAME).download(f"{empresa_id}/acta_principal_summary.json")
            acta_principal_data = json.loads(summary_bytes)
    except Exception as e:
        logger.warning(f"Error checking summary: {e}")

    return {
        "empresa_id": empresa_id,
        "nombre_empresa": empresa["nombre"],
        "bancos": bancos,
        "documentos": resultado,
        "declaraciones_sat": declaraciones_sat,
        "declaraciones_completo": declaraciones_completo,
        "acta_principal": acta_principal_data,
        "resumen": {
            "total": total,
            "aprobados": aprobados,
            "pendientes": sum(1 for d in resultado if d["estado"] == "PENDIENTE"),
            "rechazados": sum(1 for d in resultado if d["estado"] == "RECHAZADO"),
            "faltantes": sum(1 for d in resultado if d["estado"] == "FALTANTE"),
            "progreso_porcentaje": progreso,
        },
    }

@router.post("/carpetas-banco")
async def crear_carpeta_banco(
    nombre_banco: str,
    authorization: str = Header(None)
):
    """Crea una nueva carpeta de banco para la empresa."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    try:
        result = sb.table("cuentas_bancarias").insert({
            "empresa_id": empresa_id,
            "nombre_banco": nombre_banco
        }).execute()
        return result.data[0]
    except Exception as e:
        logger.error(f"Error creando cuenta bancaria: {e}")
        raise HTTPException(status_code=400, detail="La cuenta bancaria ya existe o hubo un error")

@router.delete("/carpetas-banco/{cuenta_id}")
async def eliminar_carpeta_banco(
    cuenta_id: str,
    authorization: str = Header(None)
):
    """Elimina una cuenta bancaria y sus documentos si no están aprobados."""
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    # Primero, buscar todos los documentos asociados a esta cuenta
    docs_resp = sb.table("documentos_expediente").select("id, storage_path").eq("cuenta_bancaria_id", cuenta_id).eq("empresa_id", empresa_id).execute()
    
    docs_to_delete = docs_resp.data or []
    
    # Eliminar de Storage
    for doc in docs_to_delete:
        if doc.get("storage_path"):
            try:
                sb.storage.from_("expedientes_clientes").remove([doc["storage_path"]])
            except Exception as e:
                logger.warning(f"Error eliminando de storage: {e}")
                
    # Eliminar de la base de datos (los documentos)
    if docs_to_delete:
        doc_ids = [d["id"] for d in docs_to_delete]
        sb.table("documentos_expediente").delete().in_("id", doc_ids).execute()

    # Finalmente, eliminar la cuenta bancaria
    sb.table("cuentas_bancarias").delete().eq("id", cuenta_id).eq("empresa_id", empresa_id).execute()
    return {"message": "Cuenta bancaria y documentos eliminados"}

# ══════════════════════════════════════════════════════════════════════════════
# PROCESAR ACTA PRINCIPAL (GEMINI VISION — soporta PDFs escaneados/OCR)
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_ACTA = """
Eres un analista legal experto en México.
Analiza el siguiente texto de un acta constitutiva, asamblea o poder notarial y extrae la información en formato JSON estrictamente. Si algún campo no aplica o no se encuentra, usa null.

{
  "razon_social": "Nombre completo de la empresa / sociedad",
  "tipo_documento": "Ej: Acta Constitutiva, Asamblea Extraordinaria, Poder Notarial, etc.",
  "fecha_documento": "Fecha del acta en formato YYYY-MM-DD si la encuentras, si no null",
  "accionistas": [
    "Nombre del accionista y porcentaje o número de acciones si se especifica"
  ],
  "poderes": "Resumen de quién tiene poderes legales (representantes) y qué tipo de poderes tienen",
  "resumen": "Resumen ejecutivo de máximo 3 líneas del contenido principal del documento"
}

Responde ÚNICAMENTE con el JSON, sin texto adicional, sin bloques de código markdown.

TEXTO DEL ACTA:
"""


def _ocr_with_docai(pdf_bytes: bytes) -> str:
    """Extrae texto de un PDF escaneado usando Google Cloud Document AI Basic OCR."""
    from google.cloud import documentai
    from app.config import GCP_PROJECT_ID, GCP_LOCATION, GCP_PROCESSOR_ID_BASIC_OCR, GCP_PROCESSOR_ID_OCR
    
    processor_id = GCP_PROCESSOR_ID_BASIC_OCR or GCP_PROCESSOR_ID_OCR
    if not GCP_PROJECT_ID or not processor_id:
        raise ValueError("GCP_PROJECT_ID o GCP_PROCESSOR_ID no configurados en .env")
    
    opts = {"api_endpoint": f"{GCP_LOCATION}-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts)
    name = client.processor_path(GCP_PROJECT_ID, GCP_LOCATION, processor_id)
    
    # Document AI tiene un límite de 15 páginas por llamada y 20MB
    # Procesamos en lotes si el PDF es muy grande
    doc_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    n_pages = len(doc_pdf)
    BATCH_SIZE = 15
    
    full_text = ""
    for i in range(0, n_pages, BATCH_SIZE):
        batch_doc = fitz.open()
        end = min(i + BATCH_SIZE, n_pages)
        batch_doc.insert_pdf(doc_pdf, from_page=i, to_page=end - 1)
        batch_bytes = batch_doc.tobytes()
        batch_doc.close()
        
        raw_document = documentai.RawDocument(content=batch_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = client.process_document(request=request)
        full_text += result.document.text + "\n"
        logger.info(f"DocAI OCR: páginas {i+1}-{end} de {n_pages} procesadas")
    
    doc_pdf.close()
    return full_text.strip()


def _analyze_with_vertex(text: str) -> dict:
    """Analiza el texto con Vertex AI Gemini (usa service account, sin API key)."""
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from app.config import GCP_PROJECT_ID, GCP_LOCATION
    
    # Vertex AI usa las Google Credentials del entorno (GOOGLE_APPLICATION_CREDENTIALS)
    vertexai.init(project=GCP_PROJECT_ID, location="us-central1")
    model = GenerativeModel("gemini-1.5-flash")
    
    prompt = PROMPT_ACTA + text[:30000]
    response = model.generate_content(prompt)
    
    ai_text = response.text.strip()
    # Limpiar posibles bloques markdown
    if ai_text.startswith("```json"):
        ai_text = ai_text[7:].strip()
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3].strip()
    elif ai_text.startswith("```"):
        ai_text = ai_text[3:].strip()
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3].strip()
    
    return json.loads(ai_text)


@router.post("/actas/{clave}/procesar-ia")
async def procesar_acta_principal(clave: str, authorization: str = Header(None)):
    user_info = get_user_from_token(authorization)
    sb = get_supabase_admin()

    empresa_resp = sb.table("empresas").select("id").eq("user_id", user_info["user_id"]).single().execute()
    if not empresa_resp.data:
        raise HTTPException(404, "Empresa no encontrada")
    empresa_id = empresa_resp.data["id"]

    doc_resp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).eq("tipo_documento", clave).single().execute()
    if not doc_resp.data:
        raise HTTPException(404, "Acta no encontrada")
    
    storage_path = doc_resp.data["storage_path"]
    
    # 1. Descargar el PDF
    try:
        pdf_bytes = sb.storage.from_(BUCKET_NAME).download(storage_path)
    except Exception as e:
        raise HTTPException(500, f"Error al descargar el PDF: {e}")

    # 2. Intentar extracción de texto nativo primero (PDFs digitales — gratis)
    text_content = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc[:30]:
            text_content += page.get_text() + "\n"
        doc.close()
    except Exception as e:
        logger.warning(f"No se pudo extraer texto nativo: {e}")

    # 3. Si el PDF es escaneado (sin texto), usar Document AI OCR
    if not text_content.strip() or len(text_content.strip()) < 100:
        logger.info("PDF sin texto nativo → usando Document AI Basic OCR")
        try:
            text_content = _ocr_with_docai(pdf_bytes)
        except Exception as e:
            logger.error(f"Error Document AI OCR: {e}")
            raise HTTPException(500, f"Error al procesar el PDF con OCR: {e}")

    if not text_content.strip():
        raise HTTPException(400, "No se pudo extraer texto del documento, incluso con OCR.")

    # 4. Analizar con Vertex AI Gemini
    try:
        ai_data = _analyze_with_vertex(text_content)
    except Exception as e:
        logger.error(f"Error Vertex AI: {e}")
        raise HTTPException(500, f"Error al analizar el texto con IA: {e}")

    # 5. Guardar resumen en Storage
    summary_payload = {
        "clave_principal": clave,
        "ai_summary": ai_data
    }
    
    file_path = f"{empresa_id}/acta_principal_summary.json"
    
    try:
        sb.storage.from_(BUCKET_NAME).upload(
            file=json.dumps(summary_payload, ensure_ascii=False).encode('utf-8'),
            path=file_path,
            file_options={"content-type": "application/json"}
        )
    except Exception:
        try:
            sb.storage.from_(BUCKET_NAME).update(
                file=json.dumps(summary_payload, ensure_ascii=False).encode('utf-8'),
                path=file_path,
                file_options={"content-type": "application/json"}
            )
        except Exception as e2:
            logger.error(f"Error guardando JSON en storage: {e2}")
            raise HTTPException(500, "Error guardando el resumen en Storage.")
            
    return summary_payload
