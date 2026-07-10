import sys
sys.path.append(r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend")

from app.drive_service import get_drive_service

def list_drive_files():
    try:
        service = get_drive_service()
        # Search for recent files (exclude folders)
        print("Buscando los últimos archivos (excluyendo carpetas) subidos a Drive por la cuenta de servicio:")
        query = "mimeType != 'application/vnd.google-apps.folder'"
        results = service.files().list(
            q=query,
            pageSize=20,
            fields="nextPageToken, files(id, name, mimeType, parents, createdTime)",
            orderBy="createdTime desc",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print("No se encontraron archivos. Significa que los archivos no se subieron (solo se crearon las carpetas).")
        else:
            for item in items:
                print(f"- {item['name']} (ID: {item['id']}, Creado: {item.get('createdTime')})")
                
    except Exception as e:
        print(f"Error al conectar con Drive: {e}")

if __name__ == '__main__':
    list_drive_files()
