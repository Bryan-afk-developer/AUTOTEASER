import os
import io
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from app.config import BASE_DIR

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.join(BASE_DIR, "google-credentials.json")
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

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
    target_id = os.getenv("DRIVE_PARENT_ID", "1X_i_12e01QTEslvT3NvCkW6JMKKFCMVf")
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

def create_empresa_structure(service, empresa_nombre, parent_id):
    empresa_folder = find_or_create_folder(service, empresa_nombre, parent_id)
    empresa_id = empresa_folder['id']
    
    carpetas = {
        "legal": "2.1. Actas Legales",
        "financieros": "2.2. Estados Financieros",
        "estados_cuenta": "2.3. Estados de Cuenta",
        "buro_credito": "2.4. Buró de Crédito",
        "declaraciones": "2.5. Declaraciones",
        "vigentes": "2.6. Generales / Vigentes",
        "otros": "2.7. Otros Documentos",
        "representante": "1. Representante Legal"
    }
    
    estructura = {"root": empresa_folder}
    for key, name in carpetas.items():
        sub = find_or_create_folder(service, name, empresa_id)
        estructura[key] = sub['id']
        
    return estructura

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
