from __future__ import annotations

import pypdf


def load_pdf(path: str) -> list[str]:
    reader = pypdf.PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return pages
