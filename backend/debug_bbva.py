import os
from pathlib import Path
import sys

sys.path.append(r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend")

import fitz

pdf_path = Path(r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\uploads\48aa40c8_2026.04 - BBVA 2387.pdf")
doc = fitz.open(pdf_path)
text = doc[0].get_text("text").lower()
doc.close()
print(text[:2000])
