import sys, os, pprint, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO)
from app.analytics_parser import parse_analytics, _extract_lines, _find_analytics_pages, _is_formatted_amount, _parse_number
from pathlib import Path
import pdfplumber

pdf_path = r"c:\Users\bryal\OneDrive\Escritorio\AutoTeaser\AUTOTEASER\backend\uploads\983612d9_EEFF - PORK RIND - 2025.pdf"

# Print lines specifically
pages = _find_analytics_pages(Path(pdf_path))
lines = _extract_lines(Path(pdf_path), pages)
print(f"EXTRACTED {len(lines)} LINES:")
for l in lines:
    print(f"  {l['concept'][:40]:<42} {l['amount']}")

print("\nGROUPS:")
r = parse_analytics(pdf_path)
print(f"Success: {r['success']}")
for g in r.get('groups', []):
    print(f"{g['parent_concept']} = {g['parent_total']} (sum: {g['children_sum']}, diff: {g['diff']}) [Verified: {g['verified']}]")
    for c in g['children']:
        print(f"  - {c['concept'][:30]} = {c['amount']}")

print("\nTEST PARSE NUMBER:")
print("1,771,507 ->", _parse_number('1,771,507'))
print("10.27 ->", _parse_number('10.27'))
print("11,336 ->", _parse_number('11,336'))
