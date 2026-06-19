"""
test_pipeline.py - Test script that processes PDFs through Document AI and Gemini.
Outputs the raw JSON response from each step to files in output/test_pipeline/.
"""
import json
import os
import sys
import io
import logging
from pathlib import Path

# Force UTF-8 output to avoid Windows cp1252 encoding errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure the backend directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_pipeline")

# Set Google credentials
creds_path = Path(__file__).resolve().parent / "Google-Credentials.json"
if creds_path.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)
    logger.info(f"Google credentials set: {creds_path}")
else:
    logger.warning(f"Google-Credentials.json not found at {creds_path}")

from app.doc_ai_parser import parse_pdf_with_doc_ai
from app.llm_processor import analyze_document


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "test_pipeline"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# PDFs to test (all except brightec)
PDF_FILES = [
    TEMPLATES_DIR / "EEFF - MAYA GAS - 2023.pdf",
    TEMPLATES_DIR / "EEFF - PORK RIND - 2025.pdf",
    TEMPLATES_DIR / "EEFF - SISTEMAS PROYECTOS Y VIVIENDA - 2026.03.pdf",
]


def save_json(data, filepath):
    """Save dict to JSON file, handling non-serializable objects."""
    def default_serializer(obj):
        return str(obj)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=default_serializer)
    logger.info(f"  -> Saved to {filepath}")


def test_pdf(pdf_path: Path):
    """Process a single PDF through Document AI and then Gemini."""
    stem = pdf_path.stem
    safe_stem = stem.replace(" ", "_")
    logger.info(f"")
    logger.info(f"{'='*80}")
    logger.info(f"PROCESSING: {pdf_path.name}")
    logger.info(f"{'='*80}")

    docai_result = None
    text_for_gemini = ""

    # -- Step 1: Document AI --
    logger.info(f"[1/2] Running Document AI Form Parser...")
    try:
        docai_result = parse_pdf_with_doc_ai(str(pdf_path))
        
        # Remove the non-serializable _docai_document before saving
        docai_json = {k: v for k, v in docai_result.items() if k != "_docai_document"}
        
        docai_out = OUTPUT_DIR / f"{safe_stem}_DOCAI.json"
        save_json(docai_json, docai_out)
        
        logger.info(f"  Document AI success={docai_result.get('success')}, method={docai_result.get('method')}")
        
        # Build text for Gemini from raw_text_dump
        if docai_result.get("success") and docai_result.get("raw_text_dump"):
            for year, lines in docai_result["raw_text_dump"].items():
                text_for_gemini = "\n".join(lines)
                logger.info(f"  Extracted {len(lines)} lines from DocAI for year {year}")
                
    except Exception as e:
        logger.error(f"Document AI failed: {e}", exc_info=True)
        docai_result = {"success": False, "error": str(e)}

    # -- Step 2: Gemini LLM --
    logger.info(f"[2/2] Running Gemini LLM Analysis...")
    
    if not text_for_gemini:
        # Fallback: try extracting text with PyMuPDF directly
        logger.info("  No DocAI text available, extracting with PyMuPDF...")
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            for page in doc:
                text_for_gemini += page.get_text("text") + "\n"
            doc.close()
            logger.info(f"  PyMuPDF extracted {len(text_for_gemini)} chars")
        except Exception as e:
            logger.error(f"PyMuPDF fallback failed: {e}")

    if text_for_gemini:
        try:
            gemini_result = analyze_document(text_for_gemini, doc_type="caf_brightec")
            
            gemini_out = OUTPUT_DIR / f"{safe_stem}_GEMINI.json"
            save_json(gemini_result, gemini_out)
            
            logger.info(f"  Gemini success={gemini_result.get('success')}, doc_type={gemini_result.get('document_type')}")
            
        except Exception as e:
            logger.error(f"Gemini failed: {e}", exc_info=True)
    else:
        logger.warning("No text available for Gemini analysis.")

    logger.info(f"  DONE: {pdf_path.name}")


def main():
    logger.info("="*80)
    logger.info("TEST PIPELINE: Document AI + Gemini")
    logger.info(f"PDFs to process: {len(PDF_FILES)}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("="*80)

    for pdf in PDF_FILES:
        if not pdf.exists():
            logger.warning(f"SKIPPING (not found): {pdf.name}")
            continue
        test_pdf(pdf)

    logger.info("="*80)
    logger.info("ALL TESTS COMPLETE")
    logger.info(f"Results saved to: {OUTPUT_DIR}")
    logger.info("="*80)


if __name__ == "__main__":
    main()
