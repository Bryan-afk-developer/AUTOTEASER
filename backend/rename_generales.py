"""
rename_generales.py — Renombra todos los documentos de GENERALES ya subidos al formato correcto:
  1. CSF - PM - AAAA.MM.DD           (empresa)
  2. CSF - NOMBRE APELLIDO - AAAA.MM.DD  (representante)
  2. CD - PM - AAAA.MM.DD            (empresa)
  2. CD - PF - AAAA.MM.DD            (representante)
  3. OPC - PM - AAAA.MM.DD
  4. FIEL - PM - AAAA.MM.DD          (empresa)
  4. FIEL - PF - AAAA.MM.DD          (representante)
"""
import re
import fitz  # PyMuPDF

from portal.shared.supabase_db import get_supabase_admin
from app.SAT.CSF_Location_Extractor import extract_csf_info

BUCKET = "expedientes_clientes"


def extract_date(file_bytes: bytes) -> str:
    """Extrae la fecha más reciente de un PDF en formato AAAA.MM.DD."""
    try:
        doc = fitz.open("pdf", file_bytes)
        text = ""
        for i in range(min(3, len(doc))):
            text += doc.load_page(i).get_text()
        doc.close()
        matches = re.findall(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', text)
        if matches:
            best = sorted(matches, key=lambda x: (int(x[2]), int(x[1]), int(x[0])), reverse=True)[0]
            d, m, y = best[0].zfill(2), best[1].zfill(2), best[2]
            return f"{y}.{m}.{d}"
        matches2 = re.findall(r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b', text)
        if matches2:
            best = sorted(matches2, key=lambda x: (int(x[0]), int(x[1]), int(x[2])), reverse=True)[0]
            y, m, d = best[0], best[1].zfill(2), best[2].zfill(2)
            return f"{y}.{m}.{d}"
    except Exception as e:
        print(f"    [WARN] No se pudo leer fecha: {e}")
    return ""


def build_new_name(tipo: str, file_bytes: bytes, old_name: str) -> str:
    """Construye el nombre correcto según el tipo de documento."""
    ext = ".pdf" if old_name.lower().endswith(".pdf") else \
          ("." + old_name.rsplit(".", 1)[-1] if "." in old_name else "")

    if tipo in ("csf_empresa", "csf_representante"):
        info = extract_csf_info(file_bytes=file_bytes, filename="csf.pdf")
        fecha = info.get("fecha") or extract_date(file_bytes)
        if "representante" in tipo:
            nombre = re.sub(r'[<>:"/\\|?*]', '', (info.get("nombre") or "").strip())
            if nombre and fecha:
                return f"2. CSF - {nombre} - {fecha}{ext}"
            elif nombre:
                return f"2. CSF - {nombre}{ext}"
            return f"2. CSF - PF - {fecha}{ext}" if fecha else f"2. CSF - PF{ext}"
        else:
            return f"1. CSF - PM - {fecha}{ext}" if fecha else f"1. CSF - PM{ext}"

    elif tipo in ("comprobante_domicilio_empresa", "comprobante_domicilio_representante"):
        fecha = extract_date(file_bytes)
        entity = "PF" if "representante" in tipo else "PM"
        return f"2. CD - {entity} - {fecha}{ext}" if fecha else f"2. CD - {entity}{ext}"

    elif tipo == "opinion_cumplimiento":
        fecha = extract_date(file_bytes)
        return f"3. OPC - PM - {fecha}{ext}" if fecha else f"3. OPC - PM{ext}"

    elif tipo in ("fiel_empresa", "fiel_representante", "fiel"):
        fecha = extract_date(file_bytes)
        entity = "PF" if "representante" in tipo else "PM"
        return f"4. FIEL - {entity} - {fecha}{ext}" if fecha else f"4. FIEL - {entity}{ext}"

    return old_name  # sin cambio si no corresponde


# ── Tipos a procesar ──────────────────────────────────────────────────────────
TIPOS_EXPEDIENTE = [
    "csf_empresa",
    "comprobante_domicilio_empresa",
    "opinion_cumplimiento",
    "fiel_empresa", "fiel",
]

TIPOS_REPRESENTANTE = [
    "csf_representante",
    "comprobante_domicilio_representante",
    "fiel_representante",
]

sb = get_supabase_admin()

docs_exp = sb.table("documentos_expediente").select("*").in_(
    "tipo_documento", TIPOS_EXPEDIENTE).execute().data or []
docs_rep = sb.table("documentos_representante").select("*").in_(
    "tipo_documento", TIPOS_REPRESENTANTE).execute().data or []

all_docs = [(d, "documentos_expediente") for d in docs_exp] + \
           [(d, "documentos_representante") for d in docs_rep]

print(f"Total documentos a procesar: {len(all_docs)}")
renamed = 0
errors = 0

for doc, table in all_docs:
    if not doc.get("storage_path"):
        print(f"  [SKIP] Sin archivo: {doc.get('nombre_archivo')}")
        continue

    tipo = doc["tipo_documento"]
    old_nombre = doc.get("nombre_archivo", "")
    storage_path = doc["storage_path"]

    print(f"\n{'='*60}")
    print(f"  Tipo:    {tipo}")
    print(f"  Actual:  {old_nombre}")

    # Descargar
    try:
        content = sb.storage.from_(BUCKET).download(storage_path)
    except Exception as e:
        print(f"  [ERROR] Descarga fallida: {e}")
        errors += 1
        continue

    # Construir nuevo nombre
    try:
        new_nombre = build_new_name(tipo, content, old_nombre)
    except Exception as e:
        print(f"  [ERROR] build_new_name: {e}")
        errors += 1
        continue

    print(f"  Nuevo:   {new_nombre}")

    if new_nombre == old_nombre:
        print("  [OK] Sin cambios.")
        continue

    # Subir con nuevo path
    folder = "/".join(storage_path.split("/")[:-1])
    new_path = f"{folder}/{new_nombre}"

    try:
        sb.storage.from_(BUCKET).upload(
            path=new_path, file=content,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
    except Exception as e:
        print(f"  [ERROR] Upload fallido: {e}")
        errors += 1
        continue

    # Actualizar BD
    try:
        sb.table(table).update({"nombre_archivo": new_nombre, "storage_path": new_path})\
            .eq("id", doc["id"]).execute()
    except Exception as e:
        print(f"  [ERROR] BD: {e}")
        errors += 1
        continue

    # Borrar viejo
    try:
        sb.storage.from_(BUCKET).remove([storage_path])
    except Exception as e:
        print(f"  [WARN] No se borro el viejo: {e}")

    print("  [RENAMED] OK")
    renamed += 1

print(f"\n{'='*60}")
print(f"Renombrados: {renamed} / {len(all_docs)}   Errores: {errors}")
