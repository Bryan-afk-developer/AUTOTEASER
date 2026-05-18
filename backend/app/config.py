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
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
