"""
PDF Text & Table Extraction module.

Strategy per page:
  1. pdfplumber  → extract tables as structured data (lists of lists)
  2. PyMuPDF     → extract raw text (fast, high fidelity for native PDFs)
  3. Tesseract   → OCR fallback for scanned / image-only pages

Both pdfplumber and PyMuPDF are free, fast, and excellent for native PDFs
(where you can select text with the mouse).  Tesseract is only needed when
the PDF is a scanned image.
"""
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from PIL import Image
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Main public API ───────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str | Path) -> dict:
    """
    Extract text from a PDF file using PyMuPDF + pdfplumber.

    Strategy:
      1. PyMuPDF for fast full-text extraction per page.
      2. If a page has very little text (<50 chars), fall back to OCR.

    Returns
    -------
    dict
        full_text : str          – all pages joined
        pages     : list[str]    – text per page
        method    : str          – extraction methods used
        page_count: int
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    pages_text = []
    methods_used = set()

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Try native text extraction first (PyMuPDF)
        text = page.get_text("text")

        if text and len(text.strip()) > 50:
            pages_text.append(text.strip())
            methods_used.add("pymupdf")
            logger.info(f"Page {page_num + 1}: PyMuPDF extraction ({len(text)} chars)")
        else:
            # Fall back to OCR
            ocr_text = _ocr_page(page)
            if ocr_text and len(ocr_text.strip()) > 10:
                pages_text.append(ocr_text.strip())
                methods_used.add("ocr")
                logger.info(f"Page {page_num + 1}: OCR extraction ({len(ocr_text)} chars)")
            else:
                pages_text.append(text.strip() if text else "[No text detected]")
                methods_used.add("empty")
                logger.warning(f"Page {page_num + 1}: No text detected")

    doc.close()

    full_text = "\n\n--- Page Break ---\n\n".join(pages_text)

    return {
        "full_text": full_text,
        "pages": pages_text,
        "method": ", ".join(methods_used),
        "page_count": len(pages_text),
    }


def extract_tables_from_pdf(pdf_path: str | Path) -> dict:
    """
    Extract structured tables from a PDF using pdfplumber.

    pdfplumber is specifically designed to detect table borders / gridlines
    and return clean rows & columns, making it ideal for financial statements
    that present data in tabular format.

    Returns
    -------
    dict
        tables        : list[list[list[str]]]  – list of tables, each table
                                                  is a list of rows
        tables_df     : list[dict]             – each table converted to a
                                                  pandas DataFrame then to
                                                  dict (records orientation)
        tables_count  : int
        pages_with_tables : list[int]
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    all_tables: list[list[list]] = []
    all_tables_df: list[dict] = []
    pages_with_tables: list[int] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            if not tables:
                continue

            pages_with_tables.append(page_num)

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Clean None values
                cleaned = []
                for row in table:
                    cleaned.append([
                        cell.strip() if isinstance(cell, str) else (str(cell) if cell is not None else "")
                        for cell in row
                    ])

                all_tables.append(cleaned)

                # Convert to DataFrame for easier manipulation
                try:
                    header = cleaned[0]
                    data_rows = cleaned[1:]
                    df = pd.DataFrame(data_rows, columns=header)

                    # Try to convert numeric-looking columns
                    for col in df.columns:
                        df[col] = _try_numeric(df[col])

                    all_tables_df.append({
                        "page": page_num,
                        "columns": list(df.columns),
                        "row_count": len(df),
                        "data": df.to_dict(orient="records"),
                        "preview": df.head(5).to_dict(orient="records"),
                    })
                except Exception as e:
                    logger.warning(f"Could not convert table to DataFrame: {e}")
                    all_tables_df.append({
                        "page": page_num,
                        "columns": cleaned[0] if cleaned else [],
                        "row_count": len(cleaned) - 1,
                        "data": cleaned,
                        "preview": cleaned[:6],
                    })

    logger.info(
        f"pdfplumber found {len(all_tables)} table(s) "
        f"across pages {pages_with_tables}"
    )

    return {
        "tables": all_tables,
        "tables_df": all_tables_df,
        "tables_count": len(all_tables),
        "pages_with_tables": pages_with_tables,
    }


def extract_full(pdf_path: str | Path) -> dict:
    """
    Run the complete extraction pipeline: text + tables.

    This is the recommended single-call entry point.  The result contains
    everything the LLM and the Excel filler need.
    """
    text_result = extract_text_from_pdf(pdf_path)
    tables_result = extract_tables_from_pdf(pdf_path)
    metadata = get_pdf_metadata(pdf_path)

    return {
        **text_result,
        **tables_result,
        "metadata": metadata,
    }


def get_pdf_metadata(pdf_path: str | Path) -> dict:
    """Get basic metadata from a PDF file."""
    doc = fitz.open(str(pdf_path))
    metadata = doc.metadata
    page_count = len(doc)
    doc.close()

    return {
        "title": metadata.get("title", ""),
        "author": metadata.get("author", ""),
        "page_count": page_count,
        "file_name": Path(pdf_path).name,
    }


# ── Private helpers ───────────────────────────────────────────────────────

def _ocr_page(page: fitz.Page, dpi: int = 300) -> str:
    """
    Perform OCR on a single PDF page by rendering it as an image.
    """
    try:
        import pytesseract
        from app.config import TESSERACT_CMD

        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))

        try:
            text = pytesseract.image_to_string(image, lang="spa+eng")
        except Exception:
            text = pytesseract.image_to_string(image, lang="eng")

        return text
    except ImportError:
        logger.warning("pytesseract not available, skipping OCR")
        return ""
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return ""


def _try_numeric(series: pd.Series) -> pd.Series:
    """
    Attempt to convert a pandas Series to numeric.
    Handles common financial formatting: $, commas, parentheses for negatives.
    """
    def _clean(val):
        if not isinstance(val, str):
            return val
        s = val.strip()
        if not s:
            return None
        # Remove currency symbols & thousand separators
        s = s.replace("$", "").replace(",", "").replace(" ", "")
        # Handle parentheses as negative: (1234.56) → -1234.56
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        try:
            return float(s)
        except ValueError:
            return val

    cleaned = series.apply(_clean)
    return pd.to_numeric(cleaned, errors="coerce").where(
        pd.to_numeric(cleaned, errors="coerce").notna(), other=cleaned
    )
