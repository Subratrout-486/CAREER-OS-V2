from __future__ import annotations

from pathlib import Path
from typing import Iterable


class PDFValidationError(ValueError):
    pass


class PDFRenderer:
    """Convert ATS-safe HTML to A4 PDF using Playwright-managed Chromium."""

    def render_html(self, html: str, output_path: str | Path) -> Path:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("PDF rendering requires the Playwright optional dependency") from exc

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(output),
                format="A4",
                prefer_css_page_size=True,
                print_background=True,
                margin={"top": "14mm", "right": "16mm", "bottom": "14mm", "left": "16mm"},
            )
            browser.close()
        return output


def _page_dimensions(pdf_bytes: bytes) -> Iterable[tuple[float, float]]:
    try:
        from pypdf import PdfReader
        import io
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PDF validation requires the pypdf optional dependency") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        box = page.mediabox
        yield float(box.width), float(box.height)


def validate_pdf(pdf_bytes: bytes, *, expected_text: Iterable[str] = ()) -> None:
    """Validate PDF readability, A4 geometry, and required text preservation."""
    if not pdf_bytes.startswith(b"%PDF-"):
        raise PDFValidationError("invalid PDF header")
    if len(pdf_bytes) < 500:
        raise PDFValidationError("PDF is unexpectedly small")

    try:
        from pypdf import PdfReader
        import io
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PDF validation requires the pypdf optional dependency") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        raise PDFValidationError("PDF contains no pages")

    a4_width, a4_height = 595.2756, 841.8898
    for width, height in _page_dimensions(pdf_bytes):
        if abs(width - a4_width) > 2 or abs(height - a4_height) > 2:
            raise PDFValidationError(f"page is not A4: {width:.1f} x {height:.1f} points")

    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for required in expected_text:
        if required not in text:
            raise PDFValidationError(f"required text missing from PDF: {required!r}")
