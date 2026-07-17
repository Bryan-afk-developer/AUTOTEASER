import logging
import fastapi
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import shutil
from pathlib import Path
import os
import uuid
import fitz
import base64
import time

from app.CAF.extractor import extract_tables_from_pages
from app.CAF.evidence_cropper import crop_evidence
from app.CAF.excel_builder import build_caf_excel
from app.CAF.Dictaminados.extractor_dictaminado import extract_dictaminado

router = APIRouter(prefix="/api/caf", tags=["AutoCAF v2"])
logger = logging.getLogger(__name__)

# Temporary in-memory storage for the new CAF documents
# In production this should be in a database
caf_docs = {}

UPLOAD_DIR = Path("uploads/caf_v2")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = Path("output/caf_v2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Re-populate in-memory store from files already on disk (survives hot-reload)
def _restore_caf_docs():
    restored = 0
    for pdf_file in UPLOAD_DIR.glob("*.pdf"):
        doc_id = pdf_file.stem
        if doc_id in caf_docs:
            continue
        try:
            # Try to read the original filename from sidecar metadata
            import json as _json
            meta_path = pdf_file.with_suffix(".json")
            original_filename = pdf_file.name
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta = _json.load(mf)
                    original_filename = meta.get("filename", original_filename)

            doc = fitz.open(str(pdf_file))
            page_count = len(doc)
            doc.close()
            
            # Skip generating thumbnails on startup to avoid blocking the server
            thumbnails = []

            caf_docs[doc_id] = {
                "id": doc_id,
                "filename": original_filename,
                "path": str(pdf_file),
                "page_count": page_count,
                "thumbnails": thumbnails,
                "status": "uploaded",
                "extracted_data": None,
                "excel_path": None
            }
            restored += 1
        except Exception as e:
            logger.warning(f"Could not restore doc {doc_id}: {e}")
    if restored:
        logger.info(f"Restored {restored} CAF documents from disk")


_restore_caf_docs()


class ProcessRequest(BaseModel):
    pages: List[int]
    page_layouts: dict = {}  # e.g., {"0": "single_column", "1": "two_column"}
    use_ocr: bool = True
    doc_type: str = "financiero"

class GenerateBatchExcelRequest(BaseModel):
    doc_ids: List[str]
    year_overrides: dict = {}

@router.get("/templates")
async def list_caf_templates():
    """List available Excel templates for CAF."""
    from app.config import TEMPLATES_DIR
    templates = []
    if TEMPLATES_DIR.exists():
        for f in TEMPLATES_DIR.iterdir():
            if f.suffix in (".xlsx", ".xls"):
                name = f.name.lower()
                # Name-based heuristic for CAF templates
                if "caf" in name or "balance" in name or "resultados" in name or "plantilla" in name:
                    templates.append({"name": f.name})
    return {"templates": templates}

@router.post("/empresas/{empresa_id}/export")
async def export_to_caf(empresa_id: str):
    """
    Descarga los estados financieros de la empresa desde Supabase
    y los carga directamente en la memoria local de AutoCAF.
    """
    try:
        from portal.shared.supabase_db import get_supabase_admin
        sb = get_supabase_admin()
    except Exception as e:
        logger.error(f"Error importing get_supabase_admin: {e}")
        raise HTTPException(status_code=500, detail="Error de configuración de base de datos")

    # 1. Obtener documentos de expedientes para la empresa que sean estados financieros válidos
    try:
        docs_resp = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).in_("estado", ["PENDIENTE", "APROBADO"]).execute()
    except Exception as e:
        logger.error(f"Error querying Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Error al consultar documentos: {e}")

    if not docs_resp.data:
        raise HTTPException(status_code=404, detail="No hay documentos para exportar")

    # Los estados financieros tienen "financiero" o "eeff" en tipo_documento
    eeff_docs = [d for d in docs_resp.data if ("financiero" in str(d.get("tipo_documento", "")).lower() or "eeff" in str(d.get("tipo_documento", "")).lower()) and d.get("storage_path")]
    if not eeff_docs:
        raise HTTPException(status_code=404, detail="No se encontraron Estados Financieros subidos para exportar")

    # 2. Limpiar documentos actuales de AutoCAF y sus archivos para no mezclarlos
    caf_docs.clear()
    for f in UPLOAD_DIR.glob("*"):
        try:
            f.unlink()
        except:
            pass
    for f in OUTPUT_DIR.glob("*"):
        try:
            f.unlink()
        except:
            pass

    count = 0
    import json as _json

    # 3. Descargar y procesar cada documento
    for doc in eeff_docs:
        storage_path = doc.get("storage_path")
        if not storage_path:
            continue

        try:
            file_bytes = sb.storage.from_("expedientes_clientes").download(storage_path)
            doc_id = str(uuid.uuid4())
            file_path = UPLOAD_DIR / f"{doc_id}.pdf"

            with open(file_path, "wb") as f:
                f.write(file_bytes)

            # Generar miniaturas para previsualización
            pdf = fitz.open(file_path)
            page_count = len(pdf)
            thumbnails = []
            for i in range(page_count):
                page = pdf[i]
                pix = page.get_pixmap(matrix=fitz.Matrix(0.8, 0.8))
                img_b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
                thumbnails.append({
                    "page_num": i,
                    "image": f"data:image/jpeg;base64,{img_b64}"
                })
            pdf.close()

            # Guardar metadata sidecar
            meta_path = file_path.with_suffix(".json")
            with open(meta_path, "w", encoding="utf-8") as mf:
                _json.dump({"filename": doc["nombre_archivo"]}, mf)

            caf_docs[doc_id] = {
                "id": doc_id,
                "filename": doc["nombre_archivo"],
                "path": str(file_path),
                "page_count": page_count,
                "thumbnails": thumbnails,
                "status": "uploaded",
                "extracted_data": None,
                "excel_path": None
            }
            count += 1
        except Exception as e:
            logger.error(f"Error procesando {doc['nombre_archivo']} para exportación a AutoCAF: {e}")
            continue

    return {"success": True, "count": count}

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    doc_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{doc_id}.pdf"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        doc = fitz.open(file_path)
        page_count = len(doc)
        
        # Generate thumbnails for all pages
        thumbnails = []
        for i in range(page_count):
            page = doc[i]
            # Low resolution for fast thumbnails
            pix = page.get_pixmap(matrix=fitz.Matrix(0.8, 0.8))
            img_b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            thumbnails.append({
                "page_num": i,
                "image": f"data:image/jpeg;base64,{img_b64}"
            })
            
        doc.close()
    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    caf_docs[doc_id] = {
        "id": doc_id,
        "filename": file.filename,
        "path": str(file_path),
        "page_count": page_count,
        "thumbnails": thumbnails,
        "status": "uploaded",
        "extracted_data": None,
        "excel_path": None
    }

    # Save sidecar metadata so the original filename survives server restarts
    import json as _json
    meta_path = file_path.with_suffix(".json")
    with open(meta_path, "w", encoding="utf-8") as mf:
        _json.dump({"filename": file.filename}, mf)

    return {"doc_id": doc_id, "filename": file.filename, "page_count": page_count, "thumbnails": thumbnails}

@router.post("/process/{doc_id}")
async def process_pdf(doc_id: str, request: ProcessRequest):
    if doc_id not in caf_docs:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc_info = caf_docs[doc_id]
    doc_info["status"] = "processing"
    doc_info["page_layouts"] = request.page_layouts
    
    try:
        # Extract tables
        logger.info(f"CAF: Processing {doc_info['filename']}, pages: {request.pages}, layouts: {request.page_layouts}, use_ocr: {request.use_ocr}, doc_type: {request.doc_type}")
        t0 = time.time()
        
        if request.doc_type == "dictaminado":
            result = extract_dictaminado(doc_info["path"], request.pages, request.page_layouts)
        else:
            result = extract_tables_from_pages(doc_info["path"], request.pages, request.page_layouts, request.use_ocr)
            
        logger.info(f"CAF: Extraction done in {time.time()-t0:.2f}s")
        
        # Add visual evidence crops
        for page_data in result["pages"]:
            for table in page_data["tables"]:
                for row in table:
                    valid_bboxes = [c["bbox"] for c in row if c.get("bbox")]
                    if valid_bboxes:
                        x0 = min(b[0] for b in valid_bboxes)
                        y0 = min(b[1] for b in valid_bboxes)
                        x1 = max(b[2] for b in valid_bboxes)
                        y1 = max(b[3] for b in valid_bboxes)
                        
                        b64_img = crop_evidence(doc_info["path"], page_data["page_num"], [x0, y0, x1, y1])
                        if row:
                            row[0]["evidence_b64"] = b64_img

        # Store layout mapping alongside extracted data
        result["page_layouts"] = request.page_layouts
        doc_info["extracted_data"] = result
        doc_info["status"] = "processed"
        return {"success": True, "message": "Procesado correctamente"}
        
    except Exception as e:
        doc_info["status"] = "error"
        logger.error(f"Error processing CAF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview/{doc_id}")
async def get_preview(doc_id: str):
    if doc_id not in caf_docs:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc_info = caf_docs[doc_id]
    if not doc_info["extracted_data"]:
        raise HTTPException(status_code=400, detail="Document not processed yet")
        
    return doc_info["extracted_data"]

@router.post("/generate-excel/{doc_id}")
async def generate_excel(doc_id: str):
    if doc_id not in caf_docs:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc_info = caf_docs[doc_id]
    if not doc_info["extracted_data"]:
        raise HTTPException(status_code=400, detail="Document not processed yet")
        
    try:
        excel_bytes = build_caf_excel(doc_info["extracted_data"]["pages"])
        output_filename = f"Vaciado_Crudo_{doc_info['filename']}.xlsx"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as f:
            f.write(excel_bytes)
            
        doc_info["excel_path"] = str(output_path)
        return {"success": True, "download_url": f"/api/caf/download/{doc_id}"}
        
    except Exception as e:
        logger.error(f"Error generating Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download/{doc_id}")
async def download_excel(doc_id: str):
    if doc_id not in caf_docs:
        # Fallback para excels generados en lote que sobrevivieron a un reinicio del servidor
        output_filename = f"CAF_Analisis_Consolidado_{doc_id[:8]}.xlsx"
        output_path = OUTPUT_DIR / output_filename
        if output_path.exists():
            return FileResponse(
                path=str(output_path),
                filename=output_filename,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        # Fallback para excels individuales
        single_filename = f"Vaciado_Crudo_{doc_id}.xlsx" # Simplificado, puede no funcionar si no sabemos el nombre
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc_info = caf_docs[doc_id]
    if not doc_info["excel_path"] or not os.path.exists(doc_info["excel_path"]):
        raise HTTPException(status_code=404, detail="Excel file not generated")
        
    return FileResponse(
        path=doc_info["excel_path"],
        filename=os.path.basename(doc_info["excel_path"]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.post("/generate-batch-excel")
async def generate_batch_excel(request: GenerateBatchExcelRequest):
    docs_to_build = []
    
    for doc_id in request.doc_ids:
        if doc_id in caf_docs and caf_docs[doc_id].get("extracted_data"):
            doc_info = caf_docs[doc_id]
            year = request.year_overrides.get(doc_id) or doc_info["extracted_data"].get("year", "Desconocido")
            docs_to_build.append({
                "year": year,
                "filename": doc_info["filename"],
                "extracted_data": doc_info["extracted_data"],
                "page_layouts": doc_info.get("page_layouts", {})
            })
            
    if not docs_to_build:
        raise HTTPException(status_code=400, detail="No processed documents found in the provided list.")
        
    try:
        excel_bytes = build_caf_excel(docs_to_build)
        batch_id = str(uuid.uuid4())
        output_filename = f"CAF_Analisis_Consolidado_{batch_id[:8]}.xlsx"
        output_path = OUTPUT_DIR / output_filename
        
        with open(output_path, "wb") as f:
            f.write(excel_bytes)
            
        # We need a way to download this batch excel. Let's store its path in a global dict or use the batch_id
        # For simplicity we'll just return the file directly or save it to a known path.
        # Actually, let's create a temporary doc_info entry just for the download URL
        caf_docs[batch_id] = {
            "id": batch_id,
            "excel_path": str(output_path)
        }
        
        return {"success": True, "download_url": f"/api/caf/download/{batch_id}"}
        
    except Exception as e:
        logger.error(f"Error generating batch Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/document/{doc_id}/page/{page_num}/image")
async def get_page_image(doc_id: str, page_num: int):
    if doc_id not in caf_docs:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc_info = caf_docs[doc_id]
    pdf_path = doc_info["path"]
    
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            raise HTTPException(status_code=404, detail="Page not found")
            
        page = doc[page_num]
        # High resolution for preview (e.g. 150 DPI)
        pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
        img_bytes = pix.tobytes("png")
        doc.close()
        
        return fastapi.responses.Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Error getting page image: {e}")
        raise HTTPException(status_code=500, detail="Error generating image")

@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str):
    if doc_id in caf_docs:
        doc_info = caf_docs[doc_id]
        pdf_path = Path(doc_info["path"])
        meta_path = pdf_path.with_suffix(".json")
        try:
            if pdf_path.exists(): pdf_path.unlink()
            if meta_path.exists(): meta_path.unlink()
        except:
            pass
        del caf_docs[doc_id]
    return {"success": True}

@router.get("/documents")
async def list_documents():
    docs = []
    for d in caf_docs.values():
        docs.append({
            "doc_id": d["id"],
            "filename": d["filename"],
            "page_count": d["page_count"],
            "status": d["status"],
            "thumbnails": d.get("thumbnails", []),
            "extractedData": d.get("extracted_data"),
            "pageLayouts": d.get("page_layouts", {}),
            "docType": d.get("docType", "financiero"),
            "useOcr": d.get("useOcr", True)
        })
    return {"documents": docs}
