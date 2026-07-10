import sys
import os

sys.path.append(r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend")

from app.drive_service import get_drive_service, get_shared_parent_folder

def check():
    print("Iniciando verificación de Google Drive...")
    try:
        service = get_drive_service()
        print("1. Servicio de Google Drive inicializado correctamente.")
    except Exception as e:
        print(f"Error al inicializar el servicio de Google Drive: {e}")
        return

    try:
        parent_id = get_shared_parent_folder(service)
        print(f"2. ID de carpeta padre compartido obtenido: {parent_id}")
        if parent_id == "root":
            print("   ADVERTENCIA: Se obtuvo 'root'. Esto significa que no se encontró ninguna carpeta compartida con la cuenta.")
            print("   Si estás usando Cuenta de Servicio, debes compartir la carpeta de Google Drive con el correo de la cuenta de servicio.")
    except Exception as e:
        print(f"Error al obtener la carpeta compartida: {e}")
        print("   Esto suele ocurrir si el API de Google Drive no está habilitada en Google Cloud Console, o si las credenciales son inválidas.")

if __name__ == "__main__":
    check()
