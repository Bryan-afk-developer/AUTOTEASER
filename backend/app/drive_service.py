import os
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from app.config import BASE_DIR

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.join(BASE_DIR, "google-credentials.json")
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    # Primero intentar cargar token de usuario (OAuth 2.0)
    token_path = os.path.join(BASE_DIR, "token.json")
    if os.path.exists(token_path):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        return build('drive', 'v3', credentials=creds)
        
    # Fallback a cuenta de servicio
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("No se encontró token.json ni google-credentials.json")
    
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def find_or_create_folder(service, folder_name, parent_id=None):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id and parent_id != 'root':
        query += f" and '{parent_id}' in parents"
        
    results = service.files().list(
        q=query, 
        fields="files(id, name, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = results.get('files', [])
    
    if files:
        return files[0]
    
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id and parent_id != 'root':
        file_metadata['parents'] = [parent_id]
        
    folder = service.files().create(
        body=file_metadata, 
        fields='id, name, webViewLink',
        supportsAllDrives=True
    ).execute()
    return folder

def get_shared_parent_folder(service, target_folder_name="AutoTeaser"):
    # Si hay un ID de carpeta configurado de manera explícita (el que pidió el usuario), usarlo directamente
    target_id = os.getenv("DRIVE_PARENT_ID", "1N0-ZxMPLLTUn4lZOW0YGrNCf8D4reuOz")
    if target_id:
        logger.info(f"Usando ID de carpeta padre fijo configurado manualmente: {target_id}")
        return target_id

    # Buscar si tiene acceso a algun Shared Drive (Unidad Compartida)
    drives_result = service.drives().list().execute()
    drives = drives_result.get('drives', [])
    if drives:
        for d in drives:
            if target_folder_name.lower() in d['name'].lower():
                logger.info(f"Usando Shared Drive preferido: {d['name']}")
                return d['id']
        logger.info(f"Usando Shared Drive: {drives[0]['name']}")
        return drives[0]['id']

    # Si no hay Shared Drives, buscar carpeta regular compartida
    query = "mimeType='application/vnd.google-apps.folder' and sharedWithMe=true and trashed=false"
    results = service.files().list(
        q=query, 
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = results.get('files', [])
    
    if not files:
        logger.warning("No se encontraron carpetas compartidas. Usando 'root'. ¡ADVERTENCIA! Los archivos subidos aquí no serán visibles a menos que compartas explícitamente la carpeta con el email de la Service Account.")
        return "root"
        
    for f in files:
        if target_folder_name.lower() in f['name'].lower() or "expedientes" in f['name'].lower():
            logger.info(f"Usando carpeta compartida preferida: {f['name']}")
            return f['id']
            
    logger.info(f"Usando primera carpeta compartida encontrada: {files[0]['name']}")
    return files[0]['id']

def create_empresa_structure(service, empresa_nombre, parent_id, accionistas=None, rep_name=None):
    """
    Crea la estructura de carpetas de la empresa en Google Drive:

    [PM] (empresa_nombre)
    ├── 1.1 REPRESENTANTE LEGAL (o su nombre real)
    ├── 1.X ACCIONISTAS
    └── 2. {empresa_nombre}
        ├── 1. ACTAS
        ├── 2. ESTADOS FINANCIEROS
        ├── 3. ESTADOS DE CUENTA
        │   └── [BANCO - CUENTA (BANCO XXXX)]  (dinámico)
        │       └── [AAAA]                      (dinámico)
        ├── 4. BURÓ DE CRÉDITO
        ├── 5. DECLARACIONES
        └── 6. GENERALES
    """
    if accionistas is None:
        accionistas = []
        
    empresa_folder = find_or_create_folder(service, empresa_nombre, parent_id)
    empresa_id = empresa_folder['id']

    # 1.1 Representante Legal (al nivel de la empresa)
    rep_folder_name = f"1.1 {rep_name.upper()}" if rep_name else "1.1 REPRESENTANTE LEGAL"
    rep_folder = find_or_create_folder(service, rep_folder_name, empresa_id)

    # 1.X Accionistas
    acc_folders = {}
    for acc in accionistas:
        acc_name = acc.get("nombre") or f"Accionista {acc['orden']}"
        idx = acc['orden'] + 1
        folder_name = f"1.{idx} {acc_name.upper()}"
        f_obj = find_or_create_folder(service, folder_name, empresa_id)
        acc_folders[acc['id']] = f_obj['id']

    # 2. EMPRESA (carpeta contenedora de todo lo de la empresa)
    empresa_sub = find_or_create_folder(service, f"2. {empresa_nombre}", empresa_id)
    empresa_sub_id = empresa_sub['id']

    # Subcarpetas dentro de 2. EMPRESA
    actas_folder        = find_or_create_folder(service, "1. ACTAS",              empresa_sub_id)
    financieros_folder  = find_or_create_folder(service, "2. ESTADOS FINANCIEROS", empresa_sub_id)
    ec_folder           = find_or_create_folder(service, "3. ESTADOS DE CUENTA",  empresa_sub_id)
    buro_folder         = find_or_create_folder(service, "4. BURÓ DE CRÉDITO",    empresa_sub_id)
    declaraciones_folder= find_or_create_folder(service, "5. DECLARACIONES",      empresa_sub_id)
    generales_folder    = find_or_create_folder(service, "6. GENERALES",          empresa_sub_id)

    estructura = {
        "root":         empresa_folder,
        "representante": rep_folder['id'],
        "accionistas":  acc_folders,
        "empresa_sub":  empresa_sub_id,
        "legal":        actas_folder['id'],
        "financieros":  financieros_folder['id'],
        "estados_cuenta": ec_folder['id'],
        "buro_credito": buro_folder['id'],
        "declaraciones": declaraciones_folder['id'],
        "vigentes":     generales_folder['id'],
        "otros":        generales_folder['id'],  # fallback a GENERALES
    }

    return estructura


def get_ec_subfolder(service, estructura, banco_nombre, year):
    """
    Devuelve el ID de la carpeta: 3. ESTADOS DE CUENTA > [banco_nombre] > [year]
    Crea las subcarpetas si no existen.
    """
    ec_root_id = estructura["estados_cuenta"]
    banco_folder = find_or_create_folder(service, banco_nombre, ec_root_id)
    year_folder = find_or_create_folder(service, str(year), banco_folder['id'])
    return year_folder['id']

def upload_file_to_drive(service, file_bytes, filename, mime_type, parent_id):
    query = f"name='{filename}' and '{parent_id}' in parents and trashed=false"
    results = service.files().list(
        q=query, 
        fields="files(id)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    files = results.get('files', [])
    
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    
    if files:
        file_id = files[0]['id']
        logger.info(f"El archivo {filename} ya existe en Drive. Actualizando su contenido...")
        file = service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True
        ).execute()
        return file.get('id')

    # Si no existe, lo creamos
    file_metadata = {
        'name': filename,
        'parents': [parent_id]
    }
    
    file = service.files().create(
        body=file_metadata, media_body=media, fields='id',
        supportsAllDrives=True
    ).execute()
    
    return file.get('id')
