# PDF SCANNER PRO PREMIUM

Desktop PDF toolkit built with PyQt5.

## Premium Features Included
- Create PDF from multiple images (JPG/PNG/BMP/TIFF)
- Merge multiple PDFs into one file
- Split a PDF by page range
- OCR text extraction from image/PDF sources
- One-click export of OCR text to `.txt`
- Dark modern UI with progress + activity logs

## Installation
```bash
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Notes for OCR
OCR requires external native tools in addition to Python dependencies:
- Tesseract OCR engine
- Poppler (used by `pdf2image` for PDF page conversion)

If those binaries are missing, OCR actions will show a warning while non-OCR PDF tools continue to work.
