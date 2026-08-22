from __future__ import annotations

import pypdf


def load_pdf(path: str) -> list[str]:
    """Extract text from PDF using pypdf. Works well for most PDFs."""
    reader = pypdf.PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return pages


def load_pdf_pdfplumber(path: str) -> list[str]:
    """Extract text using pdfplumber. Better for scanned/complex PDFs like IMO GMDSS."""
    import pdfplumber

    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
    return pages
