import asyncio
from portal.shared.supabase_db import get_supabase_admin

async def main():
    sb = get_supabase_admin()
    empresa_id = "2d9c5bad-3b81-4179-b065-69573c57bd32"
    
    # Simular exactamente lo que hace el backend
    table = "documentos_representante"
    doc_resp = (
        sb.table(table)
        .select("id, storage_path, nombre_archivo, estado, extracted_data")
        .eq("empresa_id", empresa_id)
        .eq("tipo_documento", "buro_representante")
        .single()
        .execute()
    )
    doc = doc_resp.data
    storage_path = doc["storage_path"]
    print(f"storage_path: {storage_path}")
    
    # Re-importar fresco para evitar cache de módulo
    import importlib
    import app.Buro_Credito.mop_extractor as m
    importlib.reload(m)
    
    resultado = m.extraer_mops_desde_storage(storage_path, sb)
    print(f"cuentas: {len(resultado.get('cuentas', []))}")
    
    # Actualizar en BD
    sb.table(table).update({"extracted_data": resultado}).eq("id", doc["id"]).execute()
    print("BD actualizada con las cuentas")

asyncio.run(main())
