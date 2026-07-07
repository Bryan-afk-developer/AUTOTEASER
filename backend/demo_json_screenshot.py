import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
import os
import sys

# Color codes for pretty terminal printing
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

load_dotenv(".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print(f"{Colors.FAIL}Error: No se encontró GEMINI_API_KEY en tu .env{Colors.ENDC}")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

prompt = """
Eres un analista financiero experto. Analiza el siguiente texto extraído de un Estado de Cuenta Bancario y devuelve EXCLUSIVAMENTE un objeto JSON estricto con las siguientes claves:
- "rfc_banco": string
- "saldo_promedio": number (sin comas ni signos)
- "cargos_totales": number
- "abonos_totales": number
- "moneda": string (MXN o USD)
- "fecha_corte": string (formato YYYY-MM-DD)

NO incluyas ninguna explicación, ni etiquetas Markdown, SOLO el JSON puro.

Texto a analizar:
BANCO NACIONAL DE MEXICO S.A.
RFC: BNM840515VB1
Fecha de Corte: 31/01/2026
Resumen del periodo:
Saldo Promedio: $ 154,230.50
Total de Cargos: $ 45,000.00
Total de Abonos: $ 78,500.25
Moneda: Pesos Mexicanos
"""

print(f"{Colors.OKCYAN}{Colors.BOLD}--- Iniciando Extracción con Inteligencia Artificial (Google Gemini) ---{Colors.ENDC}")
print(f"{Colors.HEADER}Enviando Prompt Estricto (Forzando salida JSON)...{Colors.ENDC}\n")

try:
    response = model.generate_content(prompt)
    raw_text = response.text.replace("```json", "").replace("```", "").strip()
    
    json_obj = json.loads(raw_text)
    pretty_json = json.dumps(json_obj, indent=4, ensure_ascii=False)
    
    print(f"{Colors.OKGREEN}[EXITO] Respuesta recibida exitosamente (Status: 200 OK){Colors.ENDC}")
    print(f"{Colors.WARNING}Payload procesado por Pydantic Schema Validator:{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{pretty_json}{Colors.ENDC}\n")
    print(f"{Colors.OKCYAN}{Colors.BOLD}--- Fin del Proceso ---{Colors.ENDC}")
    
except Exception as e:
    print(f"{Colors.FAIL}Error al consultar Gemini: {e}{Colors.ENDC}")
