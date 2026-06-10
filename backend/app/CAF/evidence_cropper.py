import fitz
import io
import base64
from PIL import Image

def crop_evidence(pdf_path: str, page_num: int, bbox: list[float]) -> str:
    """
    Crops a specific bounding box from a PDF page and returns it as a base64 encoded PNG.
    The bbox is expected to be [x0, y0, x1, y1] in absolute PDF coordinates.
    """
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            return ""
            
        page = doc[page_num]
        
        # Add a little padding to the bounding box for better readability
        padding = 2.0
        x0 = max(0, bbox[0] - padding)
        y0 = max(0, bbox[1] - padding)
        x1 = min(page.rect.width, bbox[2] + padding)
        y1 = min(page.rect.height, bbox[3] + padding)
        
        rect = fitz.Rect(x0, y0, x1, y1)
        
        # Render at 300 DPI for good clarity
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72), clip=rect)
        doc.close()
        
        # Convert to PIL Image to compress it
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Compress the image
        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        compressed_data = output.getvalue()
        
        # Return base64
        return base64.b64encode(compressed_data).decode("utf-8")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error cropping evidence: {e}")
        return ""
