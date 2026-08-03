"""PdfValidator birim testleri (ARCHITECTURE.md §9, §11).

Mock yok: PdfValidator dış çağrı (LLM, ağ) içermediği için tüm senaryolar
gerçek dosya baytlarıyla test edilir. Fixture'lar elle hazırlanmış minimal
PDF'lerden türetilir (TODO.md §7 — testle birlikte üretilir):
- geçerli PDF: elle kurulmuş, xref ofsetleri gerçek konumlardan hesaplanan
  tek sayfalık metinli PDF
- şifreli PDF: geçerli PDF'in pypdf.PdfWriter.encrypt() ile şifrelenmiş kopyası
- bozuk PDF: geçerli PDF'in son yarısı kesilmiş hâli (xref/EOF kaybolur)
- sahte uzantı: düz metin baytları .pdf adıyla
"""

from io import BytesIO

from pypdf import PdfReader, PdfWriter

from domain.pdf_validation import PdfValidationStatus
from services.pdf_validator import PdfValidator

# ---------------------------------------------------------------------------
# Fixture üreticileri — gerçek PDF baytları, mock değil
# ---------------------------------------------------------------------------

# 50 karakter eşiğinin (services.pdf_validator._MIN_TEXT_CHARS) rahat üstünde,
# bilinçli olarak ASCII (PDF string literal'inde encoding derdi olmasın diye).
CV_TEXT = (
    "Furkan Kaya - Yazilim Muhendisi. Python, React, SQL. "
    "5 yil backend deneyimi. Istanbul Teknik Universitesi mezunu."
)


def build_pdf_with_text(text: str) -> bytes:
    """Tek sayfalık, metin içeren minimal ama tamamen geçerli bir PDF üretir.

    xref tablosundaki ofsetler baytların gerçek konumlarından hesaplanır —
    pypdf bu dosyayı hatasız açar ve extract_text() metni aynen döndürür.
    """
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_pos,
    )
    return bytes(out)


def encrypt_pdf(pdf_bytes: bytes, user_password: str, owner_password: str | None = None) -> bytes:
    writer = PdfWriter(clone_from=BytesIO(pdf_bytes))
    writer.encrypt(user_password=user_password, owner_password=owner_password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def zero_page_pdf() -> bytes:
    buf = BytesIO()
    PdfWriter().write(buf)  # yapısal olarak geçerli, /Count 0
    return buf.getvalue()


def blank_page_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # sayfa var, metin yok
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


VALID_PDF = build_pdf_with_text(CV_TEXT)


def test_fixture_sanity_valid_pdf_is_readable():
    """Önce fixture'ın kendisi sağlam olduğunu kanıtlasın — testin testi."""
    reader = PdfReader(BytesIO(VALID_PDF))
    assert len(reader.pages) == 1
    assert "Furkan Kaya" in reader.pages[0].extract_text()


# ---------------------------------------------------------------------------
# §9 tablosu — sırayla 6 kontrol
# ---------------------------------------------------------------------------

def test_empty_file():
    result = PdfValidator.validate(b"", "cv.pdf")
    assert result.status is PdfValidationStatus.EMPTY_FILE
    assert result.user_message == "Gönderdiğin dosya boş görünüyor."
    assert result.extracted_text is None
    assert not result.is_valid


def test_txt_content_with_pdf_extension_is_not_a_pdf():
    """Uzantıya güvenilmez: .pdf adlı düz metin magic-number'da elenir."""
    result = PdfValidator.validate("Bu bir PDF degil, duz metin.".encode(), "cv.pdf")
    assert result.status is PdfValidationStatus.NOT_A_PDF


def test_encrypted_pdf():
    encrypted = encrypt_pdf(VALID_PDF, user_password="gizli123")
    result = PdfValidator.validate(encrypted, "cv.pdf")
    assert result.status is PdfValidationStatus.ENCRYPTED
    assert "şifre korumalı" in result.user_message


def test_owner_password_only_pdf_opens_with_empty_password():
    """§9: boş user-password'la açılabilen (yalnızca owner-password'lu) PDF
    şifreli SAYILMAZ — boş parola denemesi başarılı olur, akış devam eder."""
    encrypted = encrypt_pdf(VALID_PDF, user_password="", owner_password="gizli123")
    result = PdfValidator.validate(encrypted, "cv.pdf")
    assert result.status is PdfValidationStatus.VALID
    assert "Furkan Kaya" in result.extracted_text


def test_truncated_pdf_is_corrupted():
    result = PdfValidator.validate(VALID_PDF[: len(VALID_PDF) // 2], "cv.pdf")
    assert result.status is PdfValidationStatus.CORRUPTED


def test_zero_page_pdf_is_empty_pdf():
    result = PdfValidator.validate(zero_page_pdf(), "cv.pdf")
    assert result.status is PdfValidationStatus.EMPTY_PDF


def test_blank_page_has_no_extractable_text():
    result = PdfValidator.validate(blank_page_pdf(), "cv.pdf")
    assert result.status is PdfValidationStatus.NO_EXTRACTABLE_TEXT
    assert "taranmış görüntü" in result.user_message


def test_text_below_threshold_is_no_extractable_text():
    result = PdfValidator.validate(build_pdf_with_text("Kisa metin."), "cv.pdf")
    assert result.status is PdfValidationStatus.NO_EXTRACTABLE_TEXT


def test_valid_pdf():
    result = PdfValidator.validate(VALID_PDF, "cv.pdf")
    assert result.status is PdfValidationStatus.VALID
    assert result.is_valid
    assert "Furkan Kaya" in result.extracted_text
    assert "Python" in result.extracted_text
    assert result.user_message is None


def test_valid_pdf_with_wrong_extension_still_valid():
    """Ters yön: gerçek PDF, yanlış uzantıyla gelse de içerik kazanır."""
    result = PdfValidator.validate(VALID_PDF, "cv.jpg")
    assert result.status is PdfValidationStatus.VALID


def test_first_failing_check_wins():
    """Boş dosya aynı zamanda 'PDF değil' de sayılırdı — sıra gereği EMPTY_FILE döner."""
    result = PdfValidator.validate(b"", "duz-metin.txt")
    assert result.status is PdfValidationStatus.EMPTY_FILE
