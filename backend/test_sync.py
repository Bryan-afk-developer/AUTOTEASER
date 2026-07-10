import asyncio
import sys
sys.path.append(r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend")

from portal.shared.supabase_db import get_supabase_admin
from app.drive_service import get_drive_service, create_empresa_structure, get_shared_parent_folder
from portal.Admin.dashboard import background_sync_all_to_drive

def test_sync():
    empresa_id = "2d9c5bad-3b81-4179-b065-69573c57bd32"
    empresa_nombre = "SOMOS TU ÁREA COMERCIAL SAPI DE CV"
    service = get_drive_service()
    parent_id = get_shared_parent_folder(service)
    print(f"Parent ID: {parent_id}")
    
    estructura = create_empresa_structure(service, empresa_nombre, parent_id)
    print(f"Estructura: {estructura}")
    
    # We will modify background_sync to print errors instead of using logger, 
    # but for now let's just re-implement its loop here to catch the exact error!
    sb = get_supabase_admin()
    docs1 = sb.table("documentos_expediente").select("*").eq("empresa_id", empresa_id).execute()
    docs2 = sb.table("documentos_representante").select("*").eq("empresa_id", empresa_id).execute()
    all_docs = (docs1.data or []) + (docs2.data or [])
    
    from app.drive_service import upload_file_to_drive
    
    print(f"Found {len(all_docs)} docs in DB")
    for doc in all_docs:
        if not doc.get("storage_path") or doc.get("estado") in ["FALTANTE", "RECHAZADO"]:
            continue
            
        print(f"Uploading {doc['nombre_archivo']}...")
        try:
            res = sb.storage.from_("expedientes_clientes").download(doc["storage_path"])
            
            tipo_documento = doc["tipo_documento"]
            if "representante" in tipo_documento: folder_key = "representante"
            elif tipo_documento.startswith("ec_") or "estado_cuenta" in tipo_documento: folder_key = "estados_cuenta"
            elif "buro" in tipo_documento: folder_key = "buro_credito"
            elif "declaracion" in tipo_documento or "csf" in tipo_documento or "opinion" in tipo_documento: folder_key = "declaraciones"
            elif "acta" in tipo_documento or "poder" in tipo_documento: folder_key = "legal"
            elif "eeff" in tipo_documento or "estados_financieros" in tipo_documento: folder_key = "financieros"
            else: folder_key = "vigentes"
                
            folder_id = estructura[folder_key]
            
            content_type = "application/pdf"
            if doc["nombre_archivo"].endswith(".xml"): content_type = "application/xml"
            if doc["nombre_archivo"].endswith(".zip"): content_type = "application/zip"
            
            file_id = upload_file_to_drive(service, res, doc["nombre_archivo"], content_type, folder_id)
            print(f"  -> SUCCESS! File ID: {file_id}")
            break # Just test one
        except Exception as e:
            print(f"  -> ERROR syncing doc {doc.get('nombre_archivo')} to Drive: {e}")
            import traceback
            traceback.print_exc()
            break

if __name__ == '__main__':
    test_sync()
