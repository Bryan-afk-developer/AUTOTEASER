import fitz
from collections import defaultdict
import re

doc = fitz.open('backend/app/Buro_Credito/Templates/BC - HTR INFRAESTRUCTURA - 2025.11.10.pdf')
mops_por_nivel = defaultdict(lambda: defaultdict(int))
MOP_VALID={'1','2','3','4','5','6','7'}
_is_valid_year = lambda t: bool(re.match(r'^20[12][0-9]$', t))
words=[w for p in doc for w in p.get_text('words')]
lines=defaultdict(list)
[lines[round(w[1]/4)*4].append(w) for w in words]
for y in sorted(lines.keys()):
 lw=sorted(lines[y],key=lambda w:w[0])
 yw=[w for w in lw if _is_valid_year(w[4])]
 if yw:
  yx=yw[0][0]; yt=yw[0][4]
  mw=[w for w in lw if w[4] in MOP_VALID and w[0]>yx]
  for w in mw: mops_por_nivel[int(w[4])][yt] += 1
print({k: dict(v) for k,v in mops_por_nivel.items()})
