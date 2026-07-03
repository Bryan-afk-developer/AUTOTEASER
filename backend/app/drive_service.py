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
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError("No se encontró google-credentials.json")
    
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def find_or_create_folder(service, folder_name, parent_id=None):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id and parent_id != 'root':
        query += f" and '{parent_id}' in parents"
        
    results = service.files().list(q=query, fields="files(id, name, webViewLink)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]
    
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id and parent_id != 'root':
        file_metadata['parents'] = [parent_id]
        
    folder = service.files().create(body=file_metadata, fields='id, name, webViewLink').execute()
    return folder

def get_shared_parent_folder(service):
    query = "mimeType='application/vnd.google-apps.folder' and sharedWithMe=true and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    
    if not files:
        return "root"
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
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get('files', [])
    if files:
        logger.info(f"El archivo {filename} ya existe en Drive.")
        return files[0]['id']

    file_metadata = {
        'name': filename,
        'parents': [parent_id]
    }
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    
    file = service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()
    
    return file.get('id')
