import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
CLIENT_SECRETS_FILE = "oauth-client.json"

def main():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"No se encontró {CLIENT_SECRETS_FILE}.")
        return

    print("Iniciando el flujo de OAuth...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0, open_browser=False)

    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("¡token.json generado exitosamente! Ahora la app usará tu cuenta de Google.")

if __name__ == '__main__':
    main()
