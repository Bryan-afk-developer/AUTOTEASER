"""
AutoCAF - Analytics Parser (Universal Sum-Verification)

Detects parent→children groups purely by math:
  For each line, sum the next N lines. If it matches → parent with N children.
  Prefers the match with the MOST children to get the deepest breakdown.

Works on ANY PDF layout. 100% local, 0 API cost.
"""
import re
import logging
import pdfplumber
import fitz
from pathlib import Path

logger = logging.getLogger(__name__)

# ── NUMBER PARSING ──────────────────────────────────────────────

def _parse_number(raw: str) -> float:
    """Parse financial numbers robustly, handling both EU (1.234,56) and US (1,234.56) formats."""
    if not raw:
        return 0.0
    text = raw.strip()
    
    # Handle negatives
    negative = text.startswith('-') or text.startswith('(') or text.endswith(')')
    
    # Strip everything except digits, comma, period, minus
    clean = re.sub(r'[^\d.,-]', '', text)
    if clean.startswith('-'):
        clean = clean[1:]
    if not clean:
        return 0.0
        
    last_comma = clean.rfind(',')
    last_dot = clean.rfind('.')
    
    if last_comma > last_dot:
        # Comma is the last separator (e.g. 1.234,56 or 1234,56 or 1,771,507)
        after_comma = clean[last_comma + 1:]
        # If there are exactly 2 digits after the comma, it's almost certainly a decimal
        # Otherwise (like 3 digits: 507, 280), it's a thousands separator
        if len(after_comma) == 2 or len(after_comma) == 1:
            clean = clean.replace('.', '').replace(',', '.')
        else:
            clean = clean.replace(',', '')
    else:
        # Dot is the last separator, or no comma (e.g. 1,234.56 or 1234.56)
        # Assuming dot is decimal. Strip all commas.
        clean = clean.replace(',', '')
        # If there are multiple dots (e.g. OCR error 1.234.567.89), keep only the last
        if clean.count('.') > 1:
            parts = clean.split('.')
            clean = ''.join(parts[:-1]) + '.' + parts[-1]
            
    try:
        v = float(clean)
        return -v if negative else v
    except ValueError:
        return 0.0


def _is_number_text(text: str) -> bool:
    c = re.sub(r'[^0-9]', '', text.replace(',', '').replace('.', '').replace(' ', ''))
    return len(c) >= 2


def _is_skip(concept: str) -> bool:
    """Skip non-data lines (headers, footers, legal text) but NEVER skip
    legitimate child accounts (company names with S.A. DE C.V., etc.)."""
    n = concept.lower().strip()
    # Skip legal/footer boilerplate
    if any(p in n for p in ["bajo protesta", "son veraces", "responsable de la",
                             "representante legal", "manifiest", "financiera y/o",
                             "expresado en pesos", "cifras en pesos",
                             "hoja de trabajo", "pagina", "p\xe1gina"]):
        return True
    if len(concept) > 120:
        return True
    n2 = n.replace('\xed', 'i').replace('\xe1', 'a').replace('\xf1', 'n')
    # Skip page headers ("Analiticas al 31...", "Relaciones analiticas")
    # but do NOT skip company-name lines that happen to contain legal suffixes
    if any(p in n2 for p in ["analiticas al", "relaciones analiticas"]):
        return True
    return False


# ── LINE EXTRACTION ─────────────────────────────────────────────

def _is_formatted_amount(text: str) -> bool:
    """Check if text looks like a formatted financial amount (has comma/period separators).
    Distinguishes '1,234,567' (amount) from '85154414' (account number)."""
    t = text.strip().lstrip('-( ').rstrip(') ')
    # Must contain digits
    if not re.search(r'\d', t):
        return False
    # Has comma or period with digit patterns typical of amounts
    if re.search(r'\d{1,3}(,\d{3})+', t):  # e.g. 1,234,567
        return True
    if re.search(r'\d+\.\d{1,2}$', t):  # e.g. 1234.56
        return True
    if re.search(r'\d{1,3}(,\d{3})+\.\d{1,2}$', t):  # e.g. 1,234.56
        return True
    return False


def _detect_amount_threshold(pages_words: list[list[dict]], page_widths: list[float]) -> float:
    """Dynamically detect where the amount column starts across all pages.
    
    Looks at formatted numbers (with commas) and finds their typical x0 position.
    Returns the threshold as a fraction of page width, or 0.50 as default.
    """
    amount_positions = []  # (x0, page_width) tuples
    for words, pw in zip(pages_words, page_widths):
        for w in words:
            if _is_formatted_amount(w['text']):
                amount_positions.append(w['x0'] / pw)
    
    if len(amount_positions) >= 3:
        # Use the 25th percentile of amount positions (generous threshold)
        amount_positions.sort()
        p25_idx = max(0, len(amount_positions) // 4 - 1)
        threshold_pct = amount_positions[p25_idx]
        # Clamp between 35% and 80%
        threshold_pct = max(0.35, min(0.80, threshold_pct - 0.03))
        logger.info(f"Analytics: dynamic amount threshold = {threshold_pct:.0%} "
                     f"(from {len(amount_positions)} formatted amounts)")
        return threshold_pct
    
    return 0.50  # default


def _split_line_by_gap(sorted_words: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split a line of words into (concept_words, amount_words) using the widest gap.
    
    The widest gap between consecutive words on a financial line is almost always
    the gap between the concept text and the amount. This is layout-independent.
    """
    if len(sorted_words) <= 1:
        return sorted_words, []
    
    # Find the widest gap
    max_gap = 0
    max_gap_idx = -1
    for j in range(len(sorted_words) - 1):
        gap = sorted_words[j + 1]['x0'] - sorted_words[j].get('x1', sorted_words[j]['x0'] + 10)
        if gap > max_gap:
            max_gap = gap
            max_gap_idx = j
    
    # Only split if the gap is significant (> 15 points, roughly 2+ character widths)
    if max_gap > 15 and max_gap_idx >= 0:
        left = sorted_words[:max_gap_idx + 1]
        right = sorted_words[max_gap_idx + 1:]
        # Verify the right side contains at least one number
        if any(_is_number_text(w['text']) for w in right):
            return left, right
    
    return sorted_words, []


def _extract_lines(pdf_path: Path, page_indices: list[int]) -> list[dict]:
    """Extract all (concept, amount) lines from analytics pages.
    
    Uses a two-pass approach:
    1. First pass: detect the dynamic amount column threshold from formatted numbers
    2. Second pass: extract lines using BOTH gap-based splitting AND threshold-based splitting
    
    This works on ANY PDF layout regardless of where amounts are positioned.
    """
    all_lines = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        # ── First pass: collect words from all pages + detect dynamic threshold ──
        pages_data = []  # [(page_idx, page_width, words, grouped_lines)]
        all_page_words = []
        all_page_widths = []
        
        for idx in page_indices:
            if idx >= len(pdf.pages):
                continue
            page = pdf.pages[idx]
            pw = page.width
            words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=True)
            if not words:
                logger.debug(f"Analytics: page {idx+1} has no extractable words")
                continue
            
            all_page_words.append(words)
            all_page_widths.append(pw)
            
            # Group words into lines by Y proximity
            ws = sorted(words, key=lambda w: (w['top'], w['x0']))
            lines, cur, ctop = [], [], -999
            for w in ws:
                if abs(w['top'] - ctop) > 5:
                    if cur:
                        lines.append(cur)
                    cur, ctop = [w], w['top']
                else:
                    cur.append(w)
            if cur:
                lines.append(cur)
            
            pages_data.append((idx, pw, words, lines))
        
        if not pages_data:
            logger.warning("Analytics: no pages with extractable words found")
            return []
        
        # Dynamic threshold detection
        threshold_pct = _detect_amount_threshold(all_page_words, all_page_widths)
        
        # ── Second pass: extract concept-amount pairs ──
        for idx, pw, words, lines in pages_data:
            amt_x = pw * threshold_pct
            page_line_count = 0
            
            for lw in lines:
                sorted_words = sorted(lw, key=lambda w: w['x0'])
                
                # METHOD 1: Gap-based splitting (layout-independent, preferred)
                gap_left, gap_right = _split_line_by_gap(sorted_words)
                
                # METHOD 2: Threshold-based splitting (uses dynamic threshold)
                thr_left = [w for w in sorted_words 
                           if not (w['x0'] >= amt_x and _is_number_text(w['text']))]
                thr_right = [w for w in sorted_words 
                            if w['x0'] >= amt_x and _is_number_text(w['text'])]
                
                # Choose the method that gives us the best result:
                # - Prefer the method that finds an amount
                # - If both find amounts, prefer gap-based (more precise)
                # - If neither finds an amount, use gap-based for concept-only line
                if gap_right and any(_is_number_text(w['text']) for w in gap_right):
                    left, right = gap_left, gap_right
                elif thr_right:
                    left, right = thr_left, thr_right
                else:
                    left, right = gap_left, gap_right
                
                if not left:
                    continue
                
                concept = ' '.join(
                    w['text'] for w in sorted(left, key=lambda w: w['x0'])
                ).strip()
                
                if not concept or _is_skip(concept):
                    continue
                
                amount = 0.0
                if right:
                    amt_text = ' '.join(
                        w['text'] for w in sorted(right, key=lambda w: w['x0'])
                    )
                    amount = _parse_number(amt_text)
                
                all_lines.append({'concept': concept, 'amount': amount})
                page_line_count += 1
            
            logger.debug(f"Analytics: page {idx+1} -> {page_line_count} lines extracted")
    
    return all_lines


# ── FORWARD-SUM GROUPING ────────────────────────────────────────

def _find_groups(lines: list[dict]) -> list[dict]:
    """
    Universal parent→children detection via forward-sum verification.
    
    For each line i with amount > 0:
      Sum lines[i+1], lines[i+2], ... until sum ≈ lines[i].amount
      If match found → i is parent, matched lines are children.
    
    Prefer matches with MORE children (deepest breakdown).
    Resolve overlaps: deepest group wins.
    """
    n = len(lines)
    MAX_CHILDREN = 200
    TOLERANCE = 2.0  # Absolute tolerance, not percentage

    # 1. Find ALL candidate groups
    candidates = []  # (parent_idx, num_children)
    for i in range(n):
        parent_amt = lines[i]['amount']
        if parent_amt == 0:
            continue
        running = 0.0
        for k in range(1, min(MAX_CHILDREN, n - i)):
            running += lines[i + k]['amount']
            if abs(running - parent_amt) <= TOLERANCE:
                candidates.append((i, k))
                break  # First match
            # Overshoot: stop if running sum exceeds parent by >10%
            if abs(parent_amt) > 0 and running > parent_amt * 1.3 and running > parent_amt + 100:
                break

    # 2. Sort: prefer MORE children (deeper breakdown)
    candidates.sort(key=lambda c: c[1], reverse=True)

    # 3. Resolve overlaps greedily
    claimed = set()
    groups = []
    for parent_idx, num_children in candidates:
        children_range = range(parent_idx + 1, parent_idx + 1 + num_children)
        # Check no overlap
        if parent_idx in claimed or any(c in claimed for c in children_range):
            continue
        # Build group
        parent = lines[parent_idx]
        children = [lines[j] for j in children_range]
        children_sum = round(sum(c['amount'] for c in children), 2)
        diff = round(abs(children_sum - parent['amount']), 2)
        groups.append({
            'parent_concept': parent['concept'],
            'parent_total': parent['amount'],
            'children': [{'concept': c['concept'], 'amount': c['amount']} for c in children],
            'children_sum': children_sum,
            'verified': diff <= TOLERANCE,
            'diff': diff,
        })
        claimed.add(parent_idx)
        claimed.update(children_range)

    # Sort groups by order of appearance
    groups.sort(key=lambda g: next(
        (i for i, l in enumerate(lines) if l['concept'] == g['parent_concept']), 999))

    return groups


# ── PUBLIC API ──────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """Normalize text for robust keyword matching across any PDF encoding."""
    import unicodedata
    # NFKD decomposition + strip combining marks (accents)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def _find_analytics_pages(pdf_path: Path) -> list[int]:
    """Find analytics pages using multiple strategies for maximum compatibility.
    
    Strategy 1: Keyword search with fitz (standard)
    Strategy 2: Keyword search with fitz + unicode normalization
    Strategy 3: Keyword search with pdfplumber (different text engine)
    Strategy 4: Fallback → ALL pages with extractable text
    
    The forward-sum algorithm is the real filter — it only keeps
    groups where the math checks out. So feeding it extra pages is safe.
    """
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)

    # ── Strategy 1: Standard keyword search with fitz ──
    for i in range(total_pages):
        text = doc[i].get_text().lower()
        if 'analitica' in text or 'anal\xedtica' in text:
            logger.info(f"Analytics: keyword found on page {i+1} (fitz standard)")
            doc.close()
            return list(range(i, total_pages))

    # ── Strategy 2: Normalized unicode search with fitz ──
    for i in range(total_pages):
        text = _normalize_text(doc[i].get_text())
        if 'analitica' in text:
            logger.info(f"Analytics: keyword found on page {i+1} (fitz normalized)")
            doc.close()
            return list(range(i, total_pages))

    doc.close()

    # ── Strategy 3: Try pdfplumber text extraction (different engine) ──
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = (page.extract_text() or '').lower()
                if 'analitica' in text or 'anal\xedtica' in text:
                    logger.info(f"Analytics: keyword found on page {i+1} (pdfplumber)")
                    return list(range(i, len(pdf.pages)))
                # Also try with words joined (handles split text)
                words = page.extract_words()
                if words:
                    joined = ' '.join(w['text'] for w in words).lower()
                    if 'analitica' in joined or 'anal\xedtica' in joined:
                        logger.info(f"Analytics: keyword found on page {i+1} (pdfplumber words)")
                        return list(range(i, len(pdf.pages)))
    except Exception as e:
        logger.warning(f"Analytics: pdfplumber keyword search failed: {e}")

    # ── Strategy 4: FALLBACK → process ALL pages with extractable text ──
    # The forward-sum algorithm will mathematically validate groups.
    # Only pages with enough text (concept+amount pairs) are useful.
    logger.warning(f"Analytics: No keyword 'analitica' found in any page. "
                   f"Falling back to ALL {total_pages} pages.")
    
    pages_with_data = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                words = page.extract_words()
                # A page is useful if it has at least 5 words with numbers
                num_words = sum(1 for w in words if _is_number_text(w['text']))
                if num_words >= 3:
                    pages_with_data.append(i)
    except Exception as e:
        logger.warning(f"Analytics: pdfplumber fallback scan failed: {e}")

    if pages_with_data:
        logger.info(f"Analytics: fallback found {len(pages_with_data)} pages with numeric data: "
                     f"{[p+1 for p in pages_with_data]}")
        return pages_with_data

    # Absolute last resort: return all pages
    return list(range(total_pages))


def _detect_year(pdf_path: Path, page_indices: list[int]) -> str:
    """Detect the fiscal year from all available pages."""
    year = "2024"
    doc = fitz.open(str(pdf_path))
    # Search all candidate pages, not just the first
    for idx in page_indices:
        if idx >= len(doc):
            continue
        text = doc[idx].get_text()
        m = re.search(
            r'(?:al\s+\d+\s+de\s+\w+\s+(?:de(?:l)?\s+)?|ejercicio\s+|a[n\xf1]o\s+)(\d{4})',
            text, re.IGNORECASE
        )
        if m:
            yr = m.group(1)
            if yr.startswith('29'):
                yr = '20' + yr[2:]
            year = yr
            break
    doc.close()
    return year


def parse_analytics(pdf_path: str | Path) -> dict:
    """Parse analytics from PDF using universal sum-verification.
    
    Works on ANY PDF layout. The algorithm:
    1. Find candidate pages (keyword search → fallback to all pages)
    2. Extract (concept, amount) lines using pdfplumber coordinates
    3. Use forward-sum verification to find parent→children groups
    4. Return only mathematically verified groups
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {"success": False, "error": f"PDF not found: {pdf_path}"}

    page_indices = _find_analytics_pages(pdf_path)
    if not page_indices:
        return {"success": False, "error": "No se encontraron paginas con datos"}

    logger.info(f"Analytics: processing pages {[i+1 for i in page_indices]}")

    lines = _extract_lines(pdf_path, page_indices)
    if not lines:
        return {"success": False, "error": "No data extracted from pages"}

    logger.info(f"Analytics: {len(lines)} lines extracted")

    year = _detect_year(pdf_path, page_indices)

    groups = _find_groups(lines)

    if not groups:
        return {
            "success": False,
            "error": f"Se extrajeron {len(lines)} lineas pero no se encontraron "
                     f"grupos padre-hijo verificables matematicamente."
        }

    verified = sum(1 for g in groups if g['verified'])
    failed = sum(1 for g in groups if not g['verified'])

    logger.info(f"Analytics: {len(groups)} groups, {verified} OK, {failed} FAIL")
    for g in groups:
        s = "OK" if g['verified'] else f"FAIL(d={g['diff']:,.0f})"
        logger.info(f"  {g['parent_concept'][:40]}: {g['parent_total']:,.2f} "
                     f"({len(g['children'])} children) [{s}]")

    return {
        "success": True,
        "year": year,
        "groups": groups,
        "total_groups": len(groups),
        "verified_count": verified,
        "failed_count": failed,
        "raw_line_count": len(lines),
    }
