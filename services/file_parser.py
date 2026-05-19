"""Extract plain text from uploaded files (PDF, TXT, DOCX)."""
import os
from pathlib import Path


def extract_text(file_path: str) -> str:
    """Return extracted text from a file. Returns empty string on failure."""
    path = Path(file_path)
    if not path.exists():
        return ""

    suffix = path.suffix.lower()
    try:
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            return _extract_pdf(file_path)
        elif suffix in (".docx", ".doc"):
            return _extract_docx(file_path)
        elif suffix in (".md", ".rst", ".csv"):
            return path.read_text(encoding="utf-8", errors="replace")
        else:
            return ""
    except Exception:
        return ""


def _extract_pdf(file_path: str) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except ImportError:
        # Fallback: try pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception:
            return "[PDF text extraction unavailable — install pdfplumber or pypdf]"


def _extract_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        return "[DOCX extraction unavailable — install python-docx]"


def truncate_context(text: str, max_chars: int = 8000) -> str:
    """Truncate extracted text to stay within context limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...content truncated for context length...]"
