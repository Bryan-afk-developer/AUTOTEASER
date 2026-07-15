"""
rename_csf.py — Renombra todos los CSF ya subidos al formato correcto:
  - Empresa:      1. CSF - RAZÓN SOCIAL - AAAA.MM.DD.pdf
  - Representante: 2. CSF - NOMBRE APELLIDO - AAAA.MM.DD.pdf
"""
import re
import sys

from portal.shared.supabase_db import get_supabase_admin
from app.SAT.CSF_Location_Extractor import extract_csf_info

BUCKET = "expedientes_clientes"

sb = get_supabase_admin()

# Buscar todos los CSF (empresa y representante) que tengan archivo
docs_emp = sb.table("documentos_expediente").select("*").in_(
    "tipo_documento", ["csf_empresa", "csf_representante"]
).execute().data or []

docs_rep = sb.table("documentos_representante").select("*").in_(
    "tipo_documento", ["csf_empresa", "csf_representante"]
).execute().data or []

all_docs = [(d, "documentos_expediente") for d in docs_emp] + \
           [(d, "documentos_representante") for d in docs_rep]

print(f"Total CSF encontrados: {len(all_docs)}")

renamed = 0
errors = 0

for doc, table in all_docs:
    if not doc.get("storage_path"):
        print(f"  [SKIP] Sin storage_path: {doc.get('nombre_archivo')}")
        continue

    tipo = doc["tipo_documento"]
    prefix = "2. CSF" if "representante" in tipo else "1. CSF"
    old_nombre = doc.get("nombre_archivo", "")
    storage_path = doc["storage_path"]

    print(f"\n{'='*60}")
    print(f"  Tabla:   {table}")
    print(f"  Tipo:    {tipo}")
    print(f"  Actual:  {old_nombre}")

    # 1. Descargar el archivo
    try:
        content = sb.storage.from_(BUCKET).download(storage_path)
    except Exception as e:
        print(f"  [ERROR] No se pudo descargar: {e}")
        errors += 1
        continue

    # 2. Extraer nombre y fecha con el nuevo extractor
    try:
        info = extract_csf_info(file_bytes=content, filename="csf.pdf")
    except Exception as e:
        print(f"  [ERROR] Extractor falló: {e}")
        errors += 1
        continue

    nombre = (info.get("nombre") or "").strip()
    fecha  = (info.get("fecha") or "").strip()

    nombre_safe = re.sub(r'[<>:"/\\|?*]', '', nombre).strip()

    # Construir nuevo nombre
    if nombre_safe and fecha:
        new_nombre = f"{prefix} - {nombre_safe} - {fecha}.pdf"
    elif nombre_safe:
        new_nombre = f"{prefix} - {nombre_safe}.pdf"
    elif fecha:
        new_nombre = f"{prefix} - {fecha}.pdf"
    else:
        print(f"  [SKIP] No se detectó nombre ni fecha en el PDF")
        continue

    print(f"  Nuevo:   {new_nombre}")

    if new_nombre == old_nombre:
        print(f"  [OK] Ya tiene el nombre correcto, sin cambios.")
        continue

    # 3. Subir con nueva ruta en Storage (misma carpeta, nuevo nombre)
    folder = "/".join(storage_path.split("/")[:-1])
    new_storage_path = f"{folder}/{new_nombre}"

    try:
        sb.storage.from_(BUCKET).upload(
            path=new_storage_path,
            file=content,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as e:
        print(f"  [ERROR] No se pudo subir con nuevo nombre: {e}")
        errors += 1
        continue

    # 4. Actualizar BD
    try:
        sb.table(table).update({
            "nombre_archivo": new_nombre,
            "storage_path": new_storage_path,
        }).eq("id", doc["id"]).execute()
    except Exception as e:
        print(f"  [ERROR] No se pudo actualizar BD: {e}")
        errors += 1
        continue

    # 5. Eliminar archivo viejo (opcional — para no desperdiciar espacio)
    try:
        sb.storage.from_(BUCKET).remove([storage_path])
    except Exception as e:
        print(f"  [WARN] No se pudo borrar el viejo: {e}")

    print(f"  [RENAMED] OK")
    renamed += 1

print(f"\n{'='*60}")
print(f"Renombrados: {renamed} / {len(all_docs)}")
print(f"Errores:     {errors}")
