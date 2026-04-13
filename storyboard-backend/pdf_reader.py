"""
Extract text from a PDF file (path or bytes).
Uses pdfplumber first for accurate extraction, then falls back to pypdf/PyPDF2.
"""
from __future__ import annotations

import io
from pathlib import Path

# Run from storyboard-backend: pip install -r requirements.txt
_PIP_HINT = "From the storyboard-backend folder run: pip install -r requirements.txt"


def extract_text_from_pdf(pdf_input: bytes | str | Path) -> str:
    """
    pdf_input: raw PDF bytes, or file path (str/Path).
    Returns extracted text (same content as in the PDF, in page order).
    """
    # 1. Try pdfplumber (best quality, preserves layout and order)
    try:
        import pdfplumber
        if isinstance(pdf_input, (str, Path)):
            with pdfplumber.open(str(pdf_input)) as pdf:
                parts = []
                for page in pdf.pages:
                    try:
                        t = page.extract_text()
                        if t:
                            parts.append(t.strip())
                    except Exception:
                        pass
                return "\n\n".join(parts).strip() if parts else ""
        else:
            with pdfplumber.open(io.BytesIO(pdf_input)) as pdf:
                parts = []
                for page in pdf.pages:
                    try:
                        t = page.extract_text()
                        if t:
                            parts.append(t.strip())
                    except Exception:
                        pass
                return "\n\n".join(parts).strip() if parts else ""
    except ImportError:
        pass

    # 2. Fall back to pypdf
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise RuntimeError(
                "PDF support not installed. " + _PIP_HINT
            )

    if isinstance(pdf_input, (str, Path)):
        reader = PdfReader(str(pdf_input))
    else:
        reader = PdfReader(io.BytesIO(pdf_input))

    parts = []
    for page in reader.pages:
        try:
            text = page.extract_text()
            if text:
                parts.append(text.strip())
        except Exception:
            pass
    return "\n\n".join(parts).strip() if parts else ""
