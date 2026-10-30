"""One-time real Poppler+Tesseract OCR canary: no user file is read."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
import pytesseract

from app.config.settings import settings
from app.parsers.pdf_parser import PDFParser


def run_ocr_canary() -> None:
    if not settings.KNOWLEDGE_PDF_OCR_ENABLED:
        raise RuntimeError("PDF OCR not enabled")
    if shutil.which("pdftoppm") is None or shutil.which("tesseract") is None:
        raise RuntimeError("OCR binaries unavailable")
    languages = set(pytesseract.get_languages(config=""))
    if not {"eng", "jpn", "ben"}.issubset(languages):
        raise RuntimeError("OCR language packs unavailable")
    with TemporaryDirectory(prefix="aqlyra-ocr-probe-") as folder:
        root = Path(folder)
        image = Image.new("RGB", (1200, 260), "white")
        draw = ImageDraw.Draw(image)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font = ImageFont.truetype(font_path, 75)
        draw.text((40, 80), "CANARY 2048", font=font, fill="black")
        pdf_path = root / "ocr-canary.pdf"
        pdf = Canvas(str(pdf_path), pagesize=(600, 200))
        pdf.drawImage(ImageReader(image), 0, 0, width=600, height=130)
        pdf.showPage()
        pdf.save()
        result = PDFParser().parse(pdf_path)
        if result.parser_name != "pypdf+ocr" or not (
            any("CANARY" in unit.content.upper() for unit in result.units)
        ):
            raise RuntimeError("Synthetic scanned PDF OCR failed")


if __name__ == "__main__":
    try:
        run_ocr_canary()
        print("KNOWLEDGE_PDF_OCR_PROBE=PASS", flush=True)
    except Exception as exc:
        print("KNOWLEDGE_PDF_OCR_PROBE=FAIL", flush=True)
        print(f"KNOWLEDGE_PDF_OCR_DIAG={type(exc).__name__}", flush=True)
        raise SystemExit(1)
