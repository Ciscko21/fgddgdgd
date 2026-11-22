import os
import re
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI(title="PDF OCR API", version="1.0.0")

MAX_UPLOAD_SIZE_MB = int(
    os.getenv("OCR_MAX_UPLOAD_SIZE_MB", os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
)
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
OCR_DPI = int(os.getenv("OCR_DPI", "300"))


def validate_pdf_bytes(contents: bytes) -> None:
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF")

    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        reader = PdfReader(bytes(contents))
        if len(reader.pages) == 0:
            raise HTTPException(status_code=422, detail="PDF contains no pages")
    except HTTPException:
        raise
    except PdfReadError as exc:
        raise HTTPException(status_code=422, detail="Corrupted or invalid PDF") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Corrupted or invalid PDF") from exc


def ocr_pdf(contents: bytes, language: str = "eng", dpi: int = OCR_DPI) -> dict:
    validate_pdf_bytes(contents)

    if not re.fullmatch(r"[A-Za-z0-9_+]+", language):
        raise HTTPException(status_code=400, detail="Invalid OCR language code")

    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="OCR dependencies are not installed on the server",
        ) from exc

    try:
        reader = PdfReader(contents)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Corrupted or invalid PDF") from exc

    try:
        pages = convert_from_bytes(contents, dpi=dpi)
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="Unable to render PDF pages"
        ) from exc

    page_results = []
    for page_number, image in enumerate(pages, start=1):
        try:
            text = pytesseract.image_to_string(image, lang=language).strip()
        except pytesseract.TesseractError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"OCR failed for page {page_number}: {exc}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"OCR engine error: {exc}"
            ) from exc
        page_results.append({"page": page_number, "text": text})

    extracted = "\n\n".join(
        page["text"] for page in page_results if page["text"]
    ).strip()
    if not extracted:
        raise HTTPException(
            status_code=422,
            detail="No text was found. The PDF may be scanned or unreadable.",
        )

    return {
        "filename": None,
        "language": language,
        "page_count": len(reader.pages),
        "text": extracted,
        "pages": page_results,
    }


@app.post("/ocr")
@app.post("/ocr/upload")
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file to OCR")],
    language: Annotated[
        str, Query(min_length=1, max_length=100, description="Tesseract language, e.g. eng")
    ] = "eng",
) -> JSONResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    if file.content_type and file.content_type not in (
        "application/pdf",
        "application/x-pdf",
    ):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds the {MAX_UPLOAD_SIZE_MB} MB size limit",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")

    result = ocr_pdf(contents, language=language)
    result["filename"] = file.filename
    return JSONResponse(content=result)
