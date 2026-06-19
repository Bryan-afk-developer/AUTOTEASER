import asyncio
from pathlib import Path
import logging

# Ensure env is loaded
from dotenv import load_dotenv
load_dotenv(Path("C:/Users/bryal/Desktop/Test-New-CAF/backend/.env"))

from app.doc_ai_parser import parse_pdf_with_doc_ai

logging.basicConfig(level=logging.INFO)

pdf_path = r"C:\Users\bryal\Desktop\Test-New-CAF\backend\uploads\caf_47745f25_EEFF - MAYA GAS - 2026.03.PDF"
print("Running DocAI parser...")
try:
    result = parse_pdf_with_doc_ai(pdf_path)
    print("Success:", result.get('success'))
    if not result.get('success'):
        print("Error details (if any):", result)
except Exception as e:
    import traceback
    traceback.print_exc()
