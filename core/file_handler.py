"""Process file attachments for AI context (text extraction + image encoding)."""
import base64
import mimetypes
import os

_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
_VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
_MAX_TEXT = 50_000


def process_file(file_path: str) -> dict:
    """
    Process a file and return an attachment dict:
      {
        "filename": str,
        "mime_type": str,
        "type": "image" | "document" | "video" | "text",
        "base64": str,   # set for images, empty otherwise
        "text":   str,   # set for documents/text, empty for images
      }
    """
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    if ext in _IMAGE_EXTS:
        return _image(file_path, filename, mime_type or "image/jpeg")
    if ext == ".pdf":
        return _pdf(file_path, filename)
    if ext in (".docx", ".doc"):
        return _docx(file_path, filename)
    if ext in (".xlsx", ".xls"):
        return _excel(file_path, filename)
    if ext == ".csv":
        return _csv(file_path, filename)
    if ext in _VIDEO_EXTS:
        return {"filename": filename, "mime_type": mime_type, "type": "video",
                "base64": "", "text": f"[Video file attached: {filename}]"}
    # Fallback: treat as plain text
    return _text(file_path, filename, mime_type)


def _image(path: str, filename: str, mime_type: str) -> dict:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return {"filename": filename, "mime_type": mime_type, "type": "image", "base64": b64, "text": ""}


def _pdf(path: str, filename: str) -> dict:
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
    except ImportError:
        text = f"[{filename}] Install pypdf to extract text: pip install pypdf"
    except Exception as exc:
        text = f"[{filename}: PDF read error — {exc}]"
    return {"filename": filename, "mime_type": "application/pdf", "type": "document",
            "base64": "", "text": text[:_MAX_TEXT]}


def _docx(path: str, filename: str) -> dict:
    try:
        import docx
        doc = docx.Document(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        text = f"[{filename}] Install python-docx to extract text: pip install python-docx"
    except Exception as exc:
        text = f"[{filename}: Word read error — {exc}]"
    return {"filename": filename, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "type": "document", "base64": "", "text": text[:_MAX_TEXT]}


def _excel(path: str, filename: str) -> dict:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        lines = []
        for sheet in wb.worksheets[:3]:
            lines.append(f"### Sheet: {sheet.title}")
            for row in sheet.iter_rows(max_row=500, values_only=True):
                lines.append("\t".join("" if c is None else str(c) for c in row))
        text = "\n".join(lines)
    except ImportError:
        text = f"[{filename}] Install openpyxl to read Excel: pip install openpyxl"
    except Exception as exc:
        text = f"[{filename}: Excel read error — {exc}]"
    return {"filename": filename, "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "type": "document", "base64": "", "text": text[:_MAX_TEXT]}


def _csv(path: str, filename: str) -> dict:
    try:
        with open(path, "r", errors="ignore") as f:
            text = f.read()
    except Exception as exc:
        text = f"[{filename}: CSV read error — {exc}]"
    return {"filename": filename, "mime_type": "text/csv", "type": "document",
            "base64": "", "text": text[:_MAX_TEXT]}


def _text(path: str, filename: str, mime_type: str) -> dict:
    try:
        with open(path, "r", errors="ignore") as f:
            text = f.read()
        return {"filename": filename, "mime_type": "text/plain", "type": "text",
                "base64": "", "text": text[:_MAX_TEXT]}
    except Exception as exc:
        return {"filename": filename, "mime_type": mime_type, "type": "unknown",
                "base64": "", "text": f"[{filename}: could not read — {exc}]"}
