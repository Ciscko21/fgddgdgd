# PDF OCR API

A FastAPI service that accepts PDF uploads, renders every page, and uses
Tesseract OCR to return extracted text.

## Run locally

Install the system OCR and PDF-rendering tools (Debian/Ubuntu):

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API allows PDFs up to 10 MB by default. Configure it with
`OCR_MAX_UPLOAD_SIZE_MB`; rendering resolution can be changed with `OCR_DPI`.

## Test the endpoint

Interactive docs are available at `http://localhost:8000/docs`.

```bash
curl -F "file=@document.pdf" \
  "http://localhost:8000/ocr?language=eng"
```

The language parameter is a Tesseract language code such as `eng`, `deu`, or
`fra`. Install additional Tesseract language packages before using them.

Example successful response:

```json
{
  "filename": "document.pdf",
  "language": "eng",
  "page_count": 2,
  "text": "Text from all OCR'd pages",
  "pages": [
    {"page": 1, "text": "Text from page 1"},
    {"page": 2, "text": "Text from page 2"}
  ]
}
```

Corrupted PDFs, PDFs with no pages, unreadable/scanned-only PDFs, oversized
files, and non-PDF uploads return clear HTTP 4xx error responses.