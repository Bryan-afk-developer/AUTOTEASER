import asyncio
from portal.shared.supabase_db import get_supabase_admin

async def main():
    sb = get_supabase_admin()
    docs = sb.table("documentos_expediente").select("*").execute().data
    paths_to_sign = [d["storage_path"] for d in docs if d.get("storage_path")]
    print(f"Paths to sign: {paths_to_sign}")
    
    if paths_to_sign:
        resp = sb.storage.from_("expedientes_clientes").create_signed_urls(paths_to_sign, 3600)
        print(f"Resp: {resp}")

if __name__ == "__main__":
    asyncio.run(main())
