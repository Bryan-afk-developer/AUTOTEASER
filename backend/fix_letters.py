import os

fixes = {
    "g├║n": "gún",
    "r├│": "ró",
    "F├ôR": "FÓR",
    "i├│n": "ión",
    "P├íg": "Pág",
    "m├ís": "más",
    "a├¡d": "aíd",
    "F├│r": "Fór",
    "I├ôN": "IÓN",
    "ÔòÉ": "─",
    "ÔöÇ": "─",
    "ÔåÆ": "→",
    "Ã”Ã¶Ã‡": "─",
    "Pâ”œÃ": "Pá",
    "Ã”Ã²Ã‰": "─",
    "Fâ”œÃ´": "FÓ",
    "Iâ”œÃ´": "IÓ",
    "â”œÃ­": "í",
    "â”œâ”‚": "ó",
    "â”œâ•‘": "ú",
    "Ã”Ã¥Ã†": "→"
}

files = [
    'app/CAF/excel_builder.py',
    'app/CAF/Dictaminados/excel_builder_dictaminado.py'
]

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    total = 0
    for bad, good in fixes.items():
        count = text.count(bad)
        if count > 0:
            text = text.replace(bad, good)
            total += count
            print(f"Replaced {count}x: {bad} -> {good} in {file}")
            
    if total > 0:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Saved {file}")
    else:
        print(f"No changes in {file}")

print("Done")
