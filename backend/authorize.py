import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    creds = None
    # Si ya existe un token, lo intentamos cargar
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # Si no hay credenciales validas, iniciamos el flujo
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('oauth-client.json'):
                print("Error: No se encontró 'oauth-client.json'. Asegúrate de descargarlo de Google Cloud Console y ponerlo aquí.")
                return
            flow = InstalledAppFlow.from_client_secrets_file('oauth-client.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Guardamos el token
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("¡Token generado exitosamente en 'token.json'!")

if __name__ == '__main__':
    main()
