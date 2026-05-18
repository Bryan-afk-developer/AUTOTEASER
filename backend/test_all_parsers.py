"""Quick test for all bank parsers (except BBVA and HSBC)."""
import sys
import pdfplumber

sys.path.insert(0, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend")

from app.banks import banamex, banorte, scotiabank, inbursa, sabadell, santander

TESTS = {
    "BANAMEX": (banamex, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\app\banks\Banks_Examples\2026.02 - BANAMEX 2093.pdf"),
    "BANORTE": (banorte, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\app\banks\Banks_Examples\2025.12 - BANORTE 0253.PDF"),
    "SCOTIABANK": (scotiabank, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\app\banks\Banks_Examples\2025.03 - SCOTIABANK 6212.pdf"),
    "INBURSA": (inbursa, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\app\banks\Banks_Examples\2025.04 - INBURSA 0014.pdf"),
    "SABADELL": (sabadell, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\app\banks\Banks_Examples\2025.10 - SABADELL 7801.pdf"),
    "SANTANDER": (santander, r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\app\banks\Banks_Examples\2025.11 - SANTANDER 1517-6.pdf"),
}

for bank_name, (module, pdf_path) in TESTS.items():
    print(f"\n{'='*50}")
    print(f"  {bank_name}")
    print(f"{'='*50}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages)
        
        result = module.parse(text, pages)
        for k, v in result.items():
            if isinstance(v, float) and v != 0:
                print(f"  {k}: {v:,.2f}")
            else:
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"  ERROR: {e}")
