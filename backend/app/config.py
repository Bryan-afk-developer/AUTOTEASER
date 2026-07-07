"""
AutoTeaser - Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create dirs if they don't exist
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Limits
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Tesseract path (for scanned PDFs)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# Google Cloud Document AI
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "").strip()
GCP_LOCATION = os.getenv("GCP_LOCATION", "us").strip()
GCP_PROCESSOR_ID_OCR = os.getenv("GCP_PROCESSOR_ID_OCR", "").strip()
GCP_PROCESSOR_ID_BASIC_OCR = os.getenv("GCP_PROCESSOR_ID_BASIC_OCR", "").strip()

# Vertex AI requires specific region (us is multi-region for DocAI)
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1").strip()
