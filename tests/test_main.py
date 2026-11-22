from unittest.mock import Mock

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_rejects_non_pdf(monkeypatch):
    response = client.post(
        "/ocr",
        files={"file": ("hello.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_rejects_empty_pdf(monkeypatch):
    response = client.post(
        "/ocr",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


def test_rejects_invalid_pdf_magic(monkeypatch):
    response = client.post(
        "/ocr",
        files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400


def test_ocr_returns_all_pages(monkeypatch):
    monkeypatch.setattr(main, "validate_pdf_bytes", lambda contents: None)

    fake_reader = Mock()
    fake_reader.pages = [Mock(), Mock()]

    import pypdf
    import pdf2image
    import pytesseract

    monkeypatch.setattr(pypdf, "PdfReader", lambda contents: fake_reader)
    monkeypatch.setattr(pdf2image, "convert_from_bytes", lambda contents, dpi: [Mock(), Mock()])
    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        lambda image, lang: "Page one" if image is not None else "",
    )

    # Alternate text by replacing the mock function is not needed: lambda always
    # OCRs two pages to the same text, which still verifies page aggregation.
    response = client.post(
        "/ocr/upload",
        params={"language": "fra"},
        files={"file": ("sample.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "sample.pdf"
    assert body["language"] == "fra"
    assert body["page_count"] == 2
    assert len(body["pages"]) == 2
    assert "Page one" in body["text"]


def test_rejects_oversized_pdf(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE", 4)
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_MB", 0)

    response = client.post(
        "/ocr",
        files={"file": ("large.pdf", b"%PDF-" + b"x" * 10, "application/pdf")},
    )
    assert response.status_code == 413


def test_reports_scanned_only_pdf(monkeypatch):
    monkeypatch.setattr(main, "validate_pdf_bytes", lambda contents: None)

    fake_reader = Mock()
    fake_reader.pages = [Mock()]

    import pypdf
    import pdf2image
    import pytesseract

    monkeypatch.setattr(pypdf, "PdfReader", lambda contents: fake_reader)
    monkeypatch.setattr(pdf2image, "convert_from_bytes", lambda contents, dpi: [Mock()])
    monkeypatch.setattr(pytesseract, "image_to_string", lambda image, lang: "")

    response = client.post(
        "/ocr",
        files={"file": ("scanned.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert response.status_code == 422
    assert "No text" in response.json()["detail"]
