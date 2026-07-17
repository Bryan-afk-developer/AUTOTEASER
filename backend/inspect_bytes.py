with open('app/CAF/excel_builder.py', 'rb') as f:
    raw = f.read()

idx = raw.find(b'Cuenta Extra')
if idx >= 0:
    segment = raw[idx:idx+25]
    print('Hex:', segment.hex())
    print('Repr:', repr(segment))
    for i, b in enumerate(segment):
        ch = chr(b) if 32 <= b < 128 else '?'
        print(f'  [{i}] 0x{b:02X}  {ch}')
else:
    print("NOT FOUND in raw bytes!")
    # Search for the original string 
    for candidate in [b'Extra\xc3\xad', b'Extra\xed']:
        idx2 = raw.find(candidate)
        print(f"  {repr(candidate)} at {idx2}")
