"""
AutoTeaser Backend - Bank Statement Processor
Main FastAPI application.
"""
import uuid
import logging
from pathlib import Path
from datetime import datetime


from app.validation import generate_validation_report, validate_balance, validate_edo_resultados
from pydantic import BaseModel
from typing import List, Optional

class DocIdsRequest(BaseModel):
    doc_ids: List[str]

class GenerateConsolidatedRequest(BaseModel):
    doc_ids: List[str]
    template_name: str

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import UPLOAD_DIR, OUTPUT_DIR, TEMPLATES_DIR, MAX_FILE_SIZE
from app.pdf_extractor import extract_text
from app.bank_detector import detect_bank
from app.banks import get_parser
from app.excel_processor import fill_template, read_template_fields

# AutoCAF Imports
import json
from typing import List, Optional
from app.pdf_extractor_caf import extract_full as extract_full_caf, get_pdf_metadata as get_pdf_metadata_caf
from app.llm_processor import (
    analyze_document as analyze_document_caf,
    analyze_with_custom_template as analyze_with_custom_template_caf,
    detect_document_type as detect_document_type_caf,
    analyze_excel_template as analyze_excel_template_caf
)
from app.excel_processor_caf import (
    fill_template as fill_template_caf,
    fill_template_with_movements as fill_template_with_movements_caf,
    read_template_fields as read_template_fields_caf,
    fill_analytics_sheet as fill_analytics_sheet_caf
)
from app.analytics_parser import parse_analytics

# Portal de Expedientes Imports
from contextlib import asynccontextmanager
from portal.shared.supabase_db import init_supabase
from portal.Cliente import auth as portal_auth
from portal.Cliente import upload as portal_upload
from portal.Cliente import expedientes as portal_expedientes
from portal.Admin import dashboard as portal_dashboard
from portal.Admin import revision as portal_revision

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa clientes externos al arrancar la aplicación."""
    try:
        init_supabase()
        logger.info("Supabase clients initialized successfully")
    except Exception as e:
        logger.warning(f"Supabase init failed (portal features disabled): {e}")
    yield

# Create app
app = FastAPI(
    title="AutoTeaser - Bank Statement Processor",
    description="Extract data from bank statement PDFs and fill Excel templates",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Portal de Expedientes — Routers
app.include_router(portal_auth.router,         prefix="/api/portal/cliente", tags=["Portal Cliente"])
app.include_router(portal_upload.router,       prefix="/api/portal/cliente", tags=["Portal Cliente"])
app.include_router(portal_expedientes.router,  prefix="/api/portal/cliente", tags=["Portal Cliente"])
app.include_router(portal_dashboard.router,    prefix="/api/portal/admin",   tags=["Portal Admin"])
app.include_router(portal_revision.router,     prefix="/api/portal/admin",   tags=["Portal Admin"])

# In-memory store
documents = {}
caf_documents = {}


# Pydantic models
class BatchFillRequest(BaseModel):
    doc_ids: list[str]
    template_name: str


class MergeTemplatesRequest(BaseModel):
    doc_ids: list[str]
    template_name: Optional[str] = None



# ── Routes ──────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "service": "AutoTeaser - Bank Statement Processor",
        "version": "0.1.0",
    }


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a bank statement PDF.
    Extracts text immediately and detects the bank.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo se aceptan archivos PDF")

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"Archivo muy grande. Máximo: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Save file
    doc_id = str(uuid.uuid4())[:8]
    safe_name = f"{doc_id}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"PDF uploaded: {safe_name} ({len(content)} bytes)")

    # Extract text
    try:
        extraction = extract_text(file_path)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(500, f"Error al extraer texto del PDF: {str(e)}")

    # Detect bank (Gemini Vision identifies the logo, text fallback if Gemini unavailable)
    detected_bank = detect_bank(pdf_path=file_path, text=extraction["full_text"])

    # Store
    doc_info = {
        "id": doc_id,
        "file_name": file.filename,
        "file_path": str(file_path),
        "uploaded_at": datetime.now().isoformat(),
        "extraction": extraction,
        "detected_bank": detected_bank,
        "status": "uploaded",
        "parsed_data": None,
        "output_file": None,
    }
    documents[doc_id] = doc_info

    return {
        "id": doc_id,
        "file_name": file.filename,
        "page_count": extraction["page_count"],
        "detected_bank": detected_bank,
        "text_preview": extraction["full_text"][:500],
        "status": "uploaded",
    }


class SetBankRequest(BaseModel):
    bank: str


@app.post("/api/documents/{doc_id}/set-bank")
async def set_document_bank(doc_id: str, request: SetBankRequest):
    """
    Asigna o cambia el banco detectado para un documento subido de forma manual.
    """
    if doc_id not in documents:
        raise HTTPException(404, f"Documento {doc_id} no encontrado")
    
    bank = request.bank.lower().strip()
    from app.bank_detector import VALID_BANKS
    if bank not in VALID_BANKS and bank != "desconocido":
        raise HTTPException(400, f"Banco no válido. Debe ser uno de: {VALID_BANKS}")
        
    documents[doc_id]["detected_bank"] = bank if bank != "desconocido" else None
    return {
        "id": doc_id,
        "detected_bank": documents[doc_id]["detected_bank"],
        "status": documents[doc_id]["status"]
    }


@app.post("/api/process/{doc_id}")
async def process_document(doc_id: str, engine: str = "gemini"):
    """
    Process the uploaded PDF with the bank-specific parser.
    """
    if doc_id not in documents:
        raise HTTPException(404, f"Documento {doc_id} no encontrado")

    doc = documents[doc_id]
    bank = doc["detected_bank"]

    if not bank:
        raise HTTPException(400, "No se pudo detectar el banco. Sube un estado de cuenta válido.")

    parser = get_parser(bank)
    if not parser:
        raise HTTPException(400, f"No hay parser implementado para el banco: {bank}")

    try:
        # Pass pdf_path as kwarg (HSBC needs it for Gemini OCR rendering)
        parse_kwargs = {}
        if bank == "hsbc":
            parse_kwargs["pdf_path"] = doc["file_path"]
            parse_kwargs["engine"] = engine
        
        parsed_data = parser.parse(
            doc["extraction"]["full_text"],
            doc["extraction"]["pages"],
            **parse_kwargs,
        )
        doc["parsed_data"] = parsed_data
        doc["status"] = "processed"
    except NotImplementedError:
        raise HTTPException(501, f"El parser de {bank} aún no está implementado")
    except Exception as e:
        logger.error(f"Parse failed for {bank}: {e}")
        doc["status"] = "error"
        raise HTTPException(500, f"Error al procesar: {str(e)}")

    return {
        "id": doc_id,
        "bank": bank,
        "status": doc["status"],
        "data": parsed_data,
    }


def _load_mapping(template_name: str) -> dict | None:
    import json
    stem = Path(template_name).stem
    possible_names = [
        f"{stem}.json",
        f"{stem.replace(' - ', '-')}.json",
        f"{stem.replace(' ', '')}.json",
        "TEASER-PLANTILLA.json"  # Ultimate fallback for the main template
    ]
    for name in possible_names:
        map_path = TEMPLATES_DIR / name
        if map_path.exists():
            logger.info(f"Loaded mapping file: {map_path.name}")
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
    logger.warning(f"No mapping JSON found for template {template_name}")
    return None


@app.post("/api/fill-template/{doc_id}")
async def fill_template_endpoint(doc_id: str, template_name: str | None = None):
    """
    Fill an Excel template with parsed data from a single document.
    """
    if doc_id not in documents:
        raise HTTPException(404, f"Documento {doc_id} no encontrado")

    doc = documents[doc_id]

    if not doc["parsed_data"]:
        raise HTTPException(400, "El documento no ha sido procesado. Usa POST /api/process/{doc_id} primero.")

    if not template_name:
        raise HTTPException(400, "Debes especificar una plantilla (template_name)")

    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise HTTPException(404, f"Plantilla {template_name} no encontrada")

    mapping = _load_mapping(template_name)

    output_name = f"{doc_id}_filled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = OUTPUT_DIR / output_name

    try:
        fill_template(
            template_path=str(template_path),
            output_path=str(output_path),
            data_list=[doc["parsed_data"]],
            mapping=mapping,
        )
    except Exception as e:
        logger.error(f"Template fill failed: {e}")
        raise HTTPException(500, f"Error al llenar plantilla: {str(e)}")

    doc["output_file"] = str(output_path)
    doc["status"] = "completed"

    return {
        "id": doc_id,
        "status": "completed",
        "output_file": output_name,
        "download_url": f"/api/download/{doc_id}",
    }


@app.post("/api/fill-template-batch")
async def fill_template_batch_endpoint(req: BatchFillRequest):
    """
    Fill an Excel template with parsed data from multiple documents (batch).
    """
    if not req.doc_ids:
        raise HTTPException(400, "No se especificaron documentos (doc_ids)")

    data_list = []
    for doc_id in req.doc_ids:
        if doc_id not in documents:
            raise HTTPException(404, f"Documento {doc_id} no encontrado")
        doc = documents[doc_id]
        if not doc.get("parsed_data"):
            raise HTTPException(400, f"El documento {doc['file_name']} no ha sido procesado.")
        data_list.append(doc["parsed_data"])

    template_path = TEMPLATES_DIR / req.template_name
    if not template_path.exists():
        raise HTTPException(404, f"Plantilla {req.template_name} no encontrada")

    mapping = _load_mapping(req.template_name)

    output_name = f"batch_filled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = OUTPUT_DIR / output_name

    try:
        fill_template(
            template_path=str(template_path),
            output_path=str(output_path),
            data_list=data_list,
            mapping=mapping,
        )
    except Exception as e:
        logger.error(f"Batch template fill failed: {e}")
        raise HTTPException(500, f"Error al llenar plantilla en lote: {str(e)}")

    batch_id = f"batch_{str(uuid.uuid4())[:4]}"
    documents[batch_id] = {
        "id": batch_id,
        "file_name": output_name,
        "detected_bank": "LOTE",
        "status": "completed",
        "uploaded_at": datetime.now().isoformat(),
        "extraction": {"page_count": 0, "full_text": ""},
        "parsed_data": None,
        "output_file": str(output_path),
    }

    return {
        "id": batch_id,
        "status": "completed",
        "output_file": output_name,
        "download_url": f"/api/download/{batch_id}",
    }


@app.post("/api/preview-batch")
async def preview_batch_endpoint(req: BatchFillRequest):
    """
    Generate a preview table of how the data would look in the Excel
    without actually generating the file.
    """
    from collections import defaultdict

    if not req.doc_ids:
        raise HTTPException(400, "No se especificaron documentos (doc_ids)")

    mapping = _load_mapping(req.template_name)
    months_order = mapping.get("months_order", ["nov", "dic", "ene", "feb", "mar", "abr", "may"]) if mapping else []

    # Group data by account
    accounts = defaultdict(dict)
    for doc_id in req.doc_ids:
        if doc_id not in documents:
            continue
        doc = documents[doc_id]
        if not doc.get("parsed_data"):
            continue
        data = doc["parsed_data"]
        acct = data.get("account_name", "").strip()
        month = data.get("month", "").lower().strip()
        if acct and month:
            accounts[acct][month] = {
                "deposits": data.get("deposits", 0.0),
                "average_balance": data.get("average_balance", 0.0),
            }

    # Build table rows
    table = []
    for acct_name in sorted(accounts.keys()):
        months_data = accounts[acct_name]
        row = {"account_name": acct_name, "months": {}}
        for m in months_order:
            if m in months_data:
                row["months"][m] = months_data[m]
            else:
                row["months"][m] = None
        table.append(row)

    return {
        "months_order": months_order,
        "accounts": table,
        "total_accounts": len(table),
    }


@app.get("/api/download/{doc_id}")
async def download_file(doc_id: str):
    """Download the filled Excel."""
    if doc_id not in documents:
        raise HTTPException(404, "Documento no encontrado")

    doc = documents[doc_id]
    if not doc.get("output_file"):
        raise HTTPException(400, "No hay archivo generado aún")

    file_path = Path(doc["output_file"])
    if not file_path.exists():
        raise HTTPException(404, "Archivo no encontrado en disco")

    return FileResponse(
        path=str(file_path),
        filename=f"AutoTeaser_{doc['file_name'].replace('.pdf', '')}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/documents")
async def list_documents():
    """List all uploaded documents."""
    docs = []
    for doc in documents.values():
        docs.append({
            "id": doc["id"],
            "file_name": doc["file_name"],
            "detected_bank": doc["detected_bank"],
            "status": doc["status"],
            "uploaded_at": doc["uploaded_at"],
            "page_count": doc["extraction"]["page_count"],
        })
    return {"documents": docs}


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document details."""
    if doc_id not in documents:
        raise HTTPException(404, "Documento no encontrado")

    doc = documents[doc_id]
    return {
        "id": doc["id"],
        "file_name": doc["file_name"],
        "detected_bank": doc["detected_bank"],
        "status": doc["status"],
        "uploaded_at": doc["uploaded_at"],
        "page_count": doc["extraction"]["page_count"],
        "parsed_data": doc["parsed_data"],
        "text_preview": doc["extraction"]["full_text"][:1000],
        "has_output": doc["output_file"] is not None,
        "download_url": f"/api/download/{doc_id}" if doc["output_file"] else None,
    }


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and its files."""
    if doc_id not in documents:
        raise HTTPException(404, "Documento no encontrado")

    doc = documents[doc_id]

    if doc.get("file_path") and Path(doc["file_path"]).exists():
        Path(doc["file_path"]).unlink()
    if doc.get("output_file") and Path(doc["output_file"]).exists():
        Path(doc["output_file"]).unlink()

    del documents[doc_id]
    return {"message": f"Documento {doc_id} eliminado"}


@app.get("/api/templates")
async def list_templates():
    """List available Excel templates for bank statements (Teaser)."""
    templates = []
    for f in TEMPLATES_DIR.iterdir():
        if f.suffix in (".xlsx", ".xls"):
            # Check sheet names to filter out CAF templates
            try:
                from openpyxl import load_workbook
                wb = load_workbook(str(f), read_only=True)
                sheet_names = [s.lower() for s in wb.sheetnames]
                wb.close()
                is_teaser = any("banco" in s or "cuenta" in s for s in sheet_names)
                if not is_teaser:
                    # Skip files without bank-related sheets
                    continue
            except Exception:
                # If error, fallback to name-based heuristic
                name = f.name.lower()
                if "caf" in name or "balance" in name or "resultados" in name:
                    continue
            
            templates.append({"name": f.name})
    return {"templates": templates}


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "documents_count": len(documents),
        "caf_documents_count": len(caf_documents),
    }


# ── AutoCAF Routes ──────────────────────────────────────────────────────

@app.post("/api/caf/upload-pdf")
async def upload_caf_pdf(file: UploadFile = File(...)):
    """Upload a PDF file for financial document processing."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo se aceptan archivos PDF")
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"Archivo muy grande. Máximo: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    doc_id = str(uuid.uuid4())[:8]
    safe_name = f"caf_{doc_id}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    logger.info(f"AutoCAF: PDF uploaded: {safe_name} ({len(content)} bytes)")
    
    try:
        extraction = extract_full_caf(file_path)
        metadata = get_pdf_metadata_caf(file_path)
        doc_type = detect_document_type_caf(extraction["full_text"])
    except Exception as e:
        logger.error(f"AutoCAF extraction failed: {e}")
        raise HTTPException(500, f"Error al extraer texto del PDF: {str(e)}")
    
    doc_info = {
        "id": doc_id,
        "file_name": file.filename,
        "file_path": str(file_path),
        "uploaded_at": datetime.now().isoformat(),
        "extraction": extraction,
        "metadata": metadata,
        "detected_type": doc_type,
        "status": "text_extracted",
        "llm_result": None,
        "output_file": None
    }
    caf_documents[doc_id] = doc_info
    
    return {
        "id": doc_id,
        "file_name": file.filename,
        "page_count": extraction["page_count"],
        "extraction_method": extraction["method"],
        "detected_type": doc_type,
        "text_preview": extraction["full_text"][:500] + "..." if len(extraction["full_text"]) > 500 else extraction["full_text"],
        "status": "text_extracted"
    }


@app.post("/api/caf/upload-template")
async def upload_caf_template(file: UploadFile = File(...)):
    """Upload an Excel template for AutoCAF."""
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx, .xls)")
    
    content = await file.read()
    file_path = TEMPLATES_DIR / file.filename
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    try:
        template_info = read_template_fields_caf(file_path)
    except Exception as e:
        raise HTTPException(500, f"Error al leer plantilla: {str(e)}")
        
    gemini_analysis = None
    try:
        gemini_analysis = analyze_excel_template_caf(template_info)
    except Exception as e:
        logger.warning(f"AutoCAF: Gemini template analysis failed: {e}")
    
    return {
        "file_name": file.filename,
        "template_info": template_info,
        "gemini_analysis": gemini_analysis,
        "status": "template_uploaded"
    }


@app.post("/api/caf/process/{doc_id}")
async def process_caf_document(doc_id: str, doc_type: str | None = None):
    """Process an uploaded PDF with the LLM/Deterministic pipeline to extract financial data."""
    if doc_id not in caf_documents:
        raise HTTPException(404, f"Documento {doc_id} no encontrado")
    
    doc = caf_documents[doc_id]
    if doc["status"] == "error":
        raise HTTPException(400, "El documento tuvo errores de extracción anteriores")
    
    text = doc["extraction"]["full_text"]
    pages = doc["extraction"].get("pages", [])
    result = None
    pdf_path = Path(doc["file_path"])
    
    needs_doc_ai = False
    
    page1_text = pages[0] if len(pages) > 0 else ""
    page2_text = pages[1] if len(pages) > 1 else ""
    
    if "[No text detected]" in page1_text or "[No text detected]" in page2_text or len(page1_text) < 50 or len(page2_text) < 50:
        logger.info(f"AutoCAF: Página 1 o 2 sin texto nativo. Es un PDF escaneado. Activando DocAI para {doc_id}")
        needs_doc_ai = True
    else:
        # 100% DETERMINISTIC PARSER (No AI)
        try:
            from app.deterministic_parser import parse_financial_pdf
            logger.info(f"AutoCAF: Intentando parser DETERMINISTA PURO para: {doc_id}")
            result = parse_financial_pdf(pdf_path)
            
            if result and result.get("success"):
                logger.info(f"AutoCAF: Determinista exitoso para {doc_id}")
            else:
                logger.warning(f"AutoCAF: Determinista falló en la extracción: {result.get('error')}. Activando DocAI.")
                needs_doc_ai = True
        except Exception as e:
            logger.error(f"AutoCAF: Error en procesador determinista: {e}. Activando DocAI.")
            needs_doc_ai = True
            
    # FALLBACK A DOCUMENT AI (FORM PARSER)
    if needs_doc_ai:
        try:
            from app.doc_ai_parser import parse_pdf_with_doc_ai
            
            result = parse_pdf_with_doc_ai(str(pdf_path), year="2024")
            if not result.get("success"):
                raise HTTPException(500, "Fallo en procesador Document AI (Fallback)")
        except Exception as e:
            logger.error(f"AutoCAF: Error en fallback Document AI: {e}")
            raise HTTPException(500, f"Error Document AI: {e}")
    
    doc["llm_result"] = result
    
    if result["success"]:
        doc["status"] = "processed"
        if result.get("searchable_pdf_path"):
            doc["searchable_pdf_path"] = result["searchable_pdf_path"]
    else:
        doc["status"] = "llm_error"
        logger.error(f"AutoCAF: Error devuelto por el procesador para {doc_id}: {result.get('error')}")
    
    return {
        "id": doc_id,
        "status": doc["status"],
        "document_type": result.get("document_type"),
        "success": result["success"],
        "method": result.get("method", "Gemini + Deterministic"),
        "data": result.get("data"),
        "error": result.get("error"),
        "warnings": result.get("warnings", []),
        "searchable_pdf_path": doc.get("searchable_pdf_path")
    }


@app.post("/api/caf/extract-analytics/{doc_id}")
async def extract_caf_analytics(doc_id: str):
    """Extract hierarchical analytics data from a CAF PDF document."""
    if doc_id not in caf_documents:
        raise HTTPException(404, f"Documento {doc_id} no encontrado")
    
    doc = caf_documents[doc_id]
    pdf_path = Path(doc["file_path"])
    
    if not pdf_path.exists():
        raise HTTPException(404, "El archivo PDF ya no existe en el servidor.")
    
    try:
        analytics_result = parse_analytics(pdf_path)
    except Exception as e:
        logger.error(f"AutoCAF Analytics: Error al extraer analíticas: {e}")
        raise HTTPException(500, f"Error al extraer analíticas: {str(e)}")
    
    if not analytics_result.get("success"):
        raise HTTPException(400, analytics_result.get("error", "No se pudieron extraer las analíticas"))
    
    # Store analytics result in the document
    doc["analytics_result"] = analytics_result
    
    return {
        "id": doc_id,
        "success": True,
        "year": analytics_result["year"],
        "line_count": analytics_result["line_count"],
        "sections": analytics_result["sections"],
        "entries": analytics_result["entries"],
    }


@app.post("/api/caf/fill-template/{doc_id}")
async def fill_caf_template_endpoint(doc_id: str, template_name: str | None = None):
    """Fill an Excel template with extracted data from a processed financial document."""
    if doc_id not in caf_documents:
        raise HTTPException(404, f"Documento {doc_id} no encontrado")
    
    doc = caf_documents[doc_id]
    if not doc["llm_result"] or not doc["llm_result"].get("success"):
        raise HTTPException(400, "El documento debe ser procesado con éxito primero.")
    
    extracted_data = doc["llm_result"]["data"]
    
    if not template_name:
        raise HTTPException(400, "Debes seleccionar una plantilla.")
    
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise HTTPException(404, f"Plantilla {template_name} no encontrada")
    
    output_name = f"filled_caf_{doc_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = OUTPUT_DIR / output_name
    
    # Load custom mapping
    custom_mapping = None
    map_path = TEMPLATES_DIR / f"{Path(template_name).stem}.json"
    if not map_path.exists():
        fallback_path = TEMPLATES_DIR / "mapa.json"
        if fallback_path.exists():
            map_path = fallback_path
            
    if map_path.exists():
        try:
            with open(map_path, 'r', encoding='utf-8') as f:
                custom_mapping = json.load(f)
            logger.info(f"AutoCAF: Cargando mapeo personalizado de {map_path.name}")
        except Exception as e:
            logger.error(f"AutoCAF: Falló al cargar mapeo: {e}")
    
    try:
        movements = extracted_data.get("movimientos", [])
        if movements and isinstance(movements, list) and len(movements) > 0:
            header_data = {k: v for k, v in extracted_data.items() if k != "movimientos"}
            fill_template_with_movements_caf(
                template_path=str(template_path),
                output_path=str(output_path),
                header_data=header_data,
                movements=movements
            )
        else:
            fill_template_caf(
                template_path=str(template_path),
                output_path=str(output_path),
                data=extracted_data,
                mapping=custom_mapping
            )
        
        # Inject analytics sheet if available
        analytics = doc.get("analytics_result")
        if not analytics or not analytics.get("success"):
            # Try to extract analytics on-the-fly
            try:
                pdf_path = Path(doc["file_path"])
                analytics = parse_analytics(pdf_path)
                if analytics.get("success"):
                    doc["analytics_result"] = analytics
            except Exception as e:
                logger.warning(f"AutoCAF: Analytics extraction failed (non-critical): {e}")
                analytics = None
        
        if analytics and analytics.get("success"):
            try:
                fill_analytics_sheet_caf(
                    workbook_path=str(output_path),
                    output_path=str(output_path),
                    analytics_data=analytics,
                )
                logger.info(f"AutoCAF: Analytics sheet injected for {doc_id}")
            except Exception as e:
                logger.warning(f"AutoCAF: Analytics sheet injection failed (non-critical): {e}")
    except Exception as e:
        logger.error(f"AutoCAF: Falló llenado de plantilla: {e}")
        raise HTTPException(500, f"Error al llenar plantilla: {str(e)}")
    
    doc["output_file"] = str(output_path)
    doc["status"] = "completed"
    
    return {
        "id": doc_id,
        "status": "completed",
        "output_file": output_name,
        "download_url": f"/api/caf/download/{doc_id}"
    }


@app.post("/api/caf/fill-multiple-templates")
async def fill_multiple_caf_templates_endpoint(request: MergeTemplatesRequest):
    """Merge and fill a single template from multiple financial documents."""
    if not request.doc_ids:
        raise HTTPException(400, "Debes seleccionar al menos un documento")
        
    if not request.template_name:
        raise HTTPException(400, "Debes seleccionar una plantilla en la interfaz.")
        
    template_path = TEMPLATES_DIR / request.template_name
    if not template_path.exists():
        raise HTTPException(404, f"Plantilla {request.template_name} no encontrada")
        
    merged_data = {"tipo_documento": "caf_brightec", "Balance": {}, "Edo de resultados": {}}
    
    for doc_id in request.doc_ids:
        doc = caf_documents.get(doc_id)
        if not doc:
            continue
            
        llm_result = doc.get("llm_result")
        if not llm_result or not llm_result.get("success"):
            continue
            
        data = llm_result.get("data", {})
        for category in ["Balance", "Edo de resultados", "balance", "estado_resultados"]:
            if category in data:
                if category not in merged_data:
                    merged_data[category] = {}
                merged_data[category].update(data[category])
                
        # Include raw_text_dump in merged_data per year
        raw_dump = llm_result.get("raw_text_dump")
        if raw_dump:
            if "raw_text_dump" not in merged_data:
                merged_data["raw_text_dump"] = {}
            # Try to get the year from Balance or Edo de resultados
            year = "Unknown"
            if "Balance" in data and data["Balance"]:
                year = list(data["Balance"].keys())[0]
            elif "Edo de resultados" in data and data["Edo de resultados"]:
                year = list(data["Edo de resultados"].keys())[0]
            merged_data["raw_text_dump"][year] = raw_dump
                
    if not merged_data.get("Balance") and not merged_data.get("Edo de resultados"):
        raise HTTPException(400, "Ninguno de los documentos seleccionados tiene datos procesados válidos")
        
    output_name = f"Merged_CAF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = OUTPUT_DIR / output_name
    
    custom_mapping = None
    map_path = TEMPLATES_DIR / f"{Path(request.template_name).stem}.json"
    if not map_path.exists():
        fallback_path = TEMPLATES_DIR / "mapa.json"
        if fallback_path.exists():
            map_path = fallback_path
            
    if map_path.exists():
        try:
            with open(map_path, 'r', encoding='utf-8') as f:
                custom_mapping = json.load(f)
        except Exception as e:
            logger.error(f"AutoCAF: Falló al cargar mapeo: {e}")
            
    try:
        fill_template_caf(
            template_path=str(template_path),
            output_path=str(output_path),
            data=merged_data,
            mapping=custom_mapping
        )
    except Exception as e:
        logger.error(f"AutoCAF: Llenado múltiple falló: {e}")
        raise HTTPException(500, f"Error al llenar plantilla: {str(e)}")
        
    # Register this merged document so it can be deleted or downloaded
    batch_id = f"caf_merged_{str(uuid.uuid4())[:4]}"
    caf_documents[batch_id] = {
        "id": batch_id,
        "file_name": output_name,
        "detected_type": "caf_brightec",
        "status": "completed",
        "uploaded_at": datetime.now().isoformat(),
        "extraction": {"page_count": 0, "full_text": ""},
        "metadata": {},
        "llm_result": {"success": True, "data": merged_data},
        "output_file": str(output_path)
    }
    
    return {
        "status": "success",
        "message": "Plantilla combinada correctamente",
        "output_file": output_name,
        "download_url": f"/api/caf/download/{batch_id}"
    }


@app.get("/api/caf/download/{doc_id}")
async def download_caf_file(doc_id: str):
    """Download filled Excel for a specific AutoCAF document."""
    if doc_id not in caf_documents:
        raise HTTPException(404, "Documento no encontrado")
        
    doc = caf_documents[doc_id]
    if not doc.get("output_file"):
        raise HTTPException(400, "No se ha generado archivo aún")
        
    file_path = Path(doc["output_file"])
    if not file_path.exists():
        raise HTTPException(404, "El archivo no existe en el disco")
        
    return FileResponse(
        path=str(file_path),
        filename=f"AutoCAF_{doc['file_name'].replace('.pdf', '')}.xlsx",
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.get("/api/caf/download-pdf/{doc_id}")
async def download_caf_pdf(doc_id: str):
    """Download the searchable PDF with invisible OCR text."""
    if doc_id not in caf_documents:
        raise HTTPException(404, "Documento no encontrado")
        
    doc = caf_documents[doc_id]
    if not doc.get("searchable_pdf_path"):
        raise HTTPException(400, "Este documento no tiene versión PDF seleccionable (OCR no fue necesario o falló)")
        
    file_path = Path(doc["searchable_pdf_path"])
    if not file_path.exists():
        raise HTTPException(404, "El archivo PDF no existe en el disco")
        
    return FileResponse(
        path=str(file_path),
        filename=f"OCR_{doc['file_name']}",
        media_type='application/pdf'
    )


@app.get("/api/caf/documents")
async def list_caf_documents():
    """List all processed AutoCAF documents."""
    docs = []
    for doc in caf_documents.values():
        docs.append({
            "id": doc["id"],
            "file_name": doc["file_name"],
            "detected_type": doc["detected_type"],
            "status": doc["status"],
            "uploaded_at": doc["uploaded_at"],
            "page_count": doc["extraction"]["page_count"] if doc["extraction"] else 0,
            "has_output": doc["output_file"] is not None
        })
    return {"documents": docs}


@app.get("/api/caf/documents/{doc_id}")
async def get_caf_document(doc_id: str):
    """Get full details of a processed AutoCAF document."""
    if doc_id not in caf_documents:
        raise HTTPException(404, "Documento no encontrado")
    
    doc = caf_documents[doc_id]
    return {
        "id": doc["id"],
        "file_name": doc["file_name"],
        "detected_type": doc["detected_type"],
        "status": doc["status"],
        "uploaded_at": doc["uploaded_at"],
        "metadata": doc.get("metadata", {}),
        "page_count": doc["extraction"]["page_count"] if doc["extraction"] else 0,
        "extraction_method": doc["extraction"]["method"] if doc["extraction"] else None,
        "extracted_text": doc["extraction"]["full_text"] if doc["extraction"] else None,
        "llm_result": doc["llm_result"],
        "has_output": doc["output_file"] is not None,
        "download_url": f"/api/caf/download/{doc_id}" if doc["output_file"] else None
    }


@app.delete("/api/caf/documents/{doc_id}")
async def delete_caf_document(doc_id: str):
    """Delete an AutoCAF document and its files."""
    if doc_id not in caf_documents:
        raise HTTPException(404, "Documento no encontrado")
        
    doc = caf_documents[doc_id]
    if doc.get("file_path") and Path(doc["file_path"]).exists():
        Path(doc["file_path"]).unlink()
        
    if doc.get("output_file") and Path(doc["output_file"]).exists():
        Path(doc["output_file"]).unlink()
        
    del caf_documents[doc_id]
    return {"message": f"Documento {doc_id} eliminado"}


@app.get("/api/caf/templates")
async def list_caf_templates():
    """List available Excel templates for AutoCAF."""
    templates = []
    for f in TEMPLATES_DIR.iterdir():
        if f.suffix in (".xlsx", ".xls"):
            # Check sheet names to filter out Teaser templates
            try:
                from openpyxl import load_workbook
                wb = load_workbook(str(f), read_only=True)
                sheet_names = [s.lower() for s in wb.sheetnames]
                wb.close()
                
                # Check if it contains "bancos", which indicates it's a Teaser template
                is_teaser = any("banco" in s or "cuenta" in s for s in sheet_names)
                # Keep if it contains balance/resultados OR doesn't look like a teaser
                is_caf = any("balance" in s or "resultados" in s or "pérdida" in s or "ganancia" in s for s in sheet_names)
                
                if is_teaser and not is_caf:
                    # Skip teaser templates for CAF
                    continue
            except Exception:
                # If error, fallback to name-based heuristic
                name = f.name.lower()
                if "teaser" in name or "banco" in name:
                    continue
            
            try:
                info = read_template_fields_caf(f)
                templates.append({
                    "name": f.name,
                    "info": info
                })
            except Exception:
                templates.append({
                    "name": f.name,
                    "info": None
                })
    return {"templates": templates}



@app.post("/api/caf/upload-batch")
async def upload_caf_batch(files: List[UploadFile] = File(...)):
    """Upload multiple PDFs for AutoCAF."""
    results = []
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            continue
        try:
            content = await file.read()
            if len(content) > 50 * 1024 * 1024:
                continue
            
            doc_id = f"caf_{str(uuid.uuid4())[:8]}"
            file_path = UPLOAD_DIR / f"{doc_id}_{file.filename}"
            with open(file_path, "wb") as f:
                f.write(content)
            
            extracted = extract_full_caf(str(file_path))
            
            caf_documents[doc_id] = {
                "id": doc_id,
                "file_name": file.filename,
                "file_path": str(file_path),
                "detected_type": "caf_brightec",
                "status": "text_extracted",
                "uploaded_at": datetime.now().isoformat(),
                "extraction": extracted,
                "metadata": {},
                "llm_result": None,
                "output_file": None
            }
            results.append(caf_documents[doc_id])
        except Exception as e:
            logger.error(f"AutoCAF: Error uploading {file.filename}: {e}")
    return {"status": "success", "documents": results}

@app.post("/api/caf/validation-summary")
async def caf_validation_summary(req: DocIdsRequest):
    """Generate validation report for a batch of processed documents."""
    docs_to_validate = []
    for doc_id in req.doc_ids:
        if doc_id in caf_documents and caf_documents[doc_id]["status"] in ("processed", "completed") and caf_documents[doc_id]["llm_result"] and caf_documents[doc_id]["llm_result"]["success"]:
            docs_to_validate.append(caf_documents[doc_id])
    
    if not docs_to_validate:
        return {"validation": None}
        
    report = generate_validation_report(docs_to_validate)
    return {"validation": report}

@app.post("/api/caf/generate-consolidated")
async def caf_generate_consolidated(req: GenerateConsolidatedRequest):
    """Merge multiple processed docs into one Excel."""
    valid_docs = []
    for doc_id in req.doc_ids:
        doc = caf_documents.get(doc_id)
        if doc and doc["llm_result"] and doc["llm_result"]["success"]:
            valid_docs.append(doc)
            
    if not valid_docs:
        raise HTTPException(400, "No valid documents provided")
        
    template_path = TEMPLATES_DIR / req.template_name
    if not template_path.exists():
        raise HTTPException(404, "Plantilla no encontrada")
        
    merged_data = {"Balance": {}, "Edo de resultados": {}}
    analytics_by_year = {}
    
    for doc in valid_docs:
        doc_data = doc["llm_result"]["data"]
        
        # Determine year for this document from the balance data
        doc_year = None
        if "Balance" in doc_data:
            for year, data in doc_data["Balance"].items():
                merged_data["Balance"][year] = data
                doc_year = year
                
        if "Edo de resultados" in doc_data:
            for year, data in doc_data["Edo de resultados"].items():
                merged_data["Edo de resultados"][year] = data
                if not doc_year:
                    doc_year = year
                    
        # Extract analytics for this specific document
        try:
            from app.analytics_parser import parse_analytics
            from pathlib import Path
            analytics_result = parse_analytics(Path(doc["file_path"]))
            if analytics_result and analytics_result.get("success"):
                actual_year = analytics_result.get("year") or doc_year or "2024"
                analytics_by_year[actual_year] = analytics_result
        except Exception as e:
            logger.warning(f"AutoCAF: Failed to extract analytics for {doc['id']}: {e}")

    merged_data["tipo_documento"] = "caf_brightec"
    
    # We pass the full dictionary of analytics grouped by year to the Excel processor
    if analytics_by_year:
        merged_data["Analíticas"] = analytics_by_year

    output_name = f"Consolidado_CAF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = OUTPUT_DIR / output_name
    
    try:
        from app.excel_processor_caf import fill_template
        import json
        mapping = None
        mapa_file = TEMPLATES_DIR / "mapa.json"
        if mapa_file.exists():
            mapping = json.loads(mapa_file.read_text(encoding='utf-8'))
            
        fill_template(
            template_path=str(template_path),
            output_path=str(output_path),
            data=merged_data,
            mapping=mapping
        )
        
        # Inject the "Analíticas" sheets if we extracted them
        if analytics_by_year:
            from app.excel_processor_caf import fill_analytics_sheet
            fill_analytics_sheet(
                workbook_path=str(output_path),
                output_path=str(output_path),
                analytics_data=analytics_by_year
            )
            
    except Exception as e:
        logger.error(f"AutoCAF: Consolidate failed: {e}")
        raise HTTPException(500, f"Error al generar consolidado: {e}")
        
    batch_id = f"caf_cons_{str(uuid.uuid4())[:4]}"
    caf_documents[batch_id] = {
        "id": batch_id,
        "file_name": output_name,
        "detected_type": "caf_brightec",
        "status": "completed",
        "uploaded_at": datetime.now().isoformat(),
        "extraction": {"page_count": 0, "full_text": ""},
        "metadata": {},
        "llm_result": {"success": True, "data": merged_data},
        "output_file": str(output_path)
    }
    
    return {
        "status": "success",
        "output_file": output_name,
        "download_url": f"/api/caf/download/{batch_id}"
    }
