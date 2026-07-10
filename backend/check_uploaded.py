import sys
sys.path.append(r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend")

from app.drive_service import get_drive_service

def list_drive_files():
    try:
        service = get_drive_service()
        # Search for recent files or folders
        print("Buscando los últimos 10 archivos subidos a Drive por la cuenta de servicio:")
        results = service.files().list(
            pageSize=10,
            fields="nextPageToken, files(id, name, mimeType, parents)",
            orderBy="createdTime desc",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            print("No se encontraron archivos. Significa que la sincronización falló o no ha terminado.")
        else:
            for item in items:
                print(f"- {item['name']} (ID: {item['id']}, Parents: {item.get('parents', [])})")
                
    except Exception as e:
        print(f"Error al conectar con Drive: {e}")

if __name__ == '__main__':
    list_drive_files()
