import json
import logging
from unified_extractor import process_document
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Procesa documentos PDF para extraer info KYC/Financiera")
    parser.add_argument("pdf_path", help="Ruta al archivo PDF a analizar")
    parser.add_argument("--type", help="Opcional: buro_credito, estado_de_cuenta, comprobante_domicilio, ine", default=None)
    
    args = parser.parse_args()
    
    print(f"\n--- Analizando: {args.pdf_path} ---")
    result = process_document(args.pdf_path, doc_type_override=args.type)
    
    print("\n--- RESULTADO (JSON) ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
