"""
Fix corrupted UTF-8 strings in excel_builder.py.
Works at raw byte level to replace the mojibake sequences.

Analysis of 'Extraída' in the file:
  i-acute (U+00ED, UTF-8: C3 AD) is stored as: C3 A2 C2 94 C2 9C C3 82 C2 A1
  This is: U+00E2 (â) + U+0094 + U+009C + U+00C2 (Â) + U+00A1 (¡)
  = 'â\x94\x9cÂ¡' which displays as '├¡' in some terminals
"""

def fix_file(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read()

    # Exact byte sequences from inspection:
    # C3 A2 C2 94 C2 9C C3 82 C2 A1 = i-acute (í)
    # Deduce others by substituting the last byte:
    #   C2 A1 = ¡ (but this is: î, í etc... we need to decode the pattern)
    # Pattern: C3 A2 C2 94 C2 9C C3 82 C2 XX
    # where XX is the second byte of the original UTF-8 two-byte sequence C3 XX
    byte_fixes = [
        # (bad_hex, correct_utf8_bytes, char_for_logging)
        # 9-byte sequences (most corrupted)
        ('c3a2c294c29cc382c2a1', bytes.fromhex('c3ad'), 'í'),  # i-acute
        ('c3a2c294c29cc382c2a9', bytes.fromhex('c3a9'), 'é'),  # e-acute
        ('c3a2c294c29cc382c2ad', bytes.fromhex('c3a1'), 'á'),  # a-acute
        ('c3a2c294c29cc382c2b3', bytes.fromhex('c3b3'), 'ó'),  # o-acute
        ('c3a2c294c29cc382c2ba', bytes.fromhex('c3ba'), 'ú'),  # u-acute
        ('c3a2c294c29cc382c2b1', bytes.fromhex('c3b1'), 'ñ'),  # n-tilde
        ('c3a2c294c29cc382c293', bytes.fromhex('c393'), 'Ó'),  # O-acute
        ('c3a2c294c29cc382c291', bytes.fromhex('c391'), 'Ñ'),  # N-tilde
        ('c3a2c294c29cc382c281', bytes.fromhex('c381'), 'Á'),  # A-acute
        ('c3a2c294c29cc382c289', bytes.fromhex('c389'), 'É'),  # E-acute
        ('c3a2c294c29cc382c29a', bytes.fromhex('c39a'), 'Ú'),  # U-acute
        ('c3a2c294c29cc382c28f', bytes.fromhex('c38f'), 'Ï'),  # I-diaeresis
        ('c3a2c294c29cc382c2bc', bytes.fromhex('c3bc'), 'ü'),  # u-diaeresis
    ]

    total = 0
    for bad_hex, good_bytes, char in byte_fixes:
        bad = bytes.fromhex(bad_hex)
        count = raw.count(bad)
        if count:
            print(f'  Fixed {count}x -> {repr(char)}')
            raw = raw.replace(bad, good_bytes)
            total += count

    print(f'  Total replacements: {total}')

    with open(filepath, 'wb') as f:
        f.write(raw)
    print(f'  Written OK.')


if __name__ == '__main__':
    import sys
    files = sys.argv[1:] if len(sys.argv) > 1 else [
        'app/CAF/excel_builder.py',
        'app/CAF/Dictaminados/excel_builder_dictaminado.py',
    ]
    for filepath in files:
        print(f'\n=== {filepath} ===')
        try:
            fix_file(filepath)
        except FileNotFoundError:
            print(f'  Not found, skipping.')
