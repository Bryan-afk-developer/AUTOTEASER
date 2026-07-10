import fitz

def main():
    doc = fitz.open("buro_test.pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        first_line = text.split("\n")[0] if text else ""
        print(f"Page {page_num+1}: {first_line[:100]}")
        
        # print first few headers of page
        headers = [line.strip() for line in text.split("\n") if "CRÉDITOS" in line or "DETALLE" in line]
        if headers:
            print(f"  Headers: {headers}")

if __name__ == '__main__':
    main()
