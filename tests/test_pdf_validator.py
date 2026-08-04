"""ARCHITECTURE.md §8 — PdfValidator birim testleri.

Mock yok: her senaryo için gerçek, elle üretilmiş PDF baytları kullanılır (pypdf ile
üretilip pypdf ile doğrulanır) çünkü servis hiçbir dış çağrı (LLM, ağ) içermiyor.
"""

import io

from pypdf import PdfWriter

import pdf_validator
from models import PdfValidationStatus


def _make_pdf_with_text(text: str) -> bytes:
    """Metin içeren, gerçekten geçerli, elle inşa edilmiş minimal bir PDF."""
    content_stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(out)


VALID_PDF = _make_pdf_with_text(
    "Ahmet Yilmaz - Senior Developer with 5 years React experience and clean code practices."
)


def _make_encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.append(io.BytesIO(VALID_PDF))
    writer.encrypt(user_password="secret123")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_zero_page_pdf() -> bytes:
    writer = PdfWriter()
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_blank_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_empty_file_rejected():
    result = pdf_validator.validate(b"")
    assert result.status == PdfValidationStatus.EMPTY_FILE


def test_non_pdf_rejected_even_with_fake_extension():
    fake = b"Bu aslinda bir metin dosyasi, cv.pdf diye yeniden adlandirilmis olabilir."
    result = pdf_validator.validate(fake)
    assert result.status == PdfValidationStatus.NOT_A_PDF


def test_encrypted_pdf_rejected():
    result = pdf_validator.validate(_make_encrypted_pdf())
    assert result.status == PdfValidationStatus.ENCRYPTED


def test_corrupted_pdf_rejected():
    truncated = VALID_PDF[: len(VALID_PDF) // 2]
    result = pdf_validator.validate(truncated)
    assert result.status == PdfValidationStatus.CORRUPTED


def test_zero_page_pdf_rejected():
    result = pdf_validator.validate(_make_zero_page_pdf())
    assert result.status == PdfValidationStatus.EMPTY_PDF


def test_blank_page_pdf_rejected():
    result = pdf_validator.validate(_make_blank_page_pdf())
    assert result.status == PdfValidationStatus.NO_EXTRACTABLE_TEXT


def test_valid_pdf_accepted_and_text_extracted():
    result = pdf_validator.validate(VALID_PDF)
    assert result.status == PdfValidationStatus.VALID
    assert result.extracted_text is not None
    assert "Ahmet Yilmaz" in result.extracted_text
    assert result.user_message is None
