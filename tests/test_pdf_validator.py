"""validate_pdf testleri — mock yok, her senaryo gerçek PDF baytlarıyla (§9'daki 6 kontrol + geçerli durum)."""

from io import BytesIO

from pypdf import PdfWriter

from pdf_validator import validate_pdf


def make_pdf(text: str) -> bytes:
    """Metin içeren minimal ama tamamen geçerli tek sayfalık PDF (xref ofsetleri gerçek)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, obj)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


CV = make_pdf("Furkan Kaya - Yazilim Muhendisi. Python, React, SQL. 5 yil backend deneyimi.")


def test_bos_dosya():
    text, err = validate_pdf(b"")
    assert text is None and "boş" in err


def test_pdf_olmayan_dosya():  # .pdf uzantılı düz metin de bu yolla yakalanır (magic bytes)
    text, err = validate_pdf("Bu bir PDF degil.".encode())
    assert text is None and "PDF değil" in err


def test_sifreli_pdf():
    writer = PdfWriter(clone_from=BytesIO(CV))
    writer.encrypt("gizli123")
    buf = BytesIO()
    writer.write(buf)
    text, err = validate_pdf(buf.getvalue())
    assert text is None and "şifre korumalı" in err


def test_bozuk_pdf():  # son yarısı kesilince xref/EOF kaybolur
    text, err = validate_pdf(CV[: len(CV) // 2])
    assert text is None and "bozuk" in err


def test_sayfasiz_pdf():
    buf = BytesIO()
    PdfWriter().write(buf)  # yapısal olarak geçerli, 0 sayfa
    text, err = validate_pdf(buf.getvalue())
    assert text is None and "hiç sayfa yok" in err


def test_metinsiz_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)  # sayfa var, metin yok
    buf = BytesIO()
    writer.write(buf)
    text, err = validate_pdf(buf.getvalue())
    assert text is None and "metin çıkaramadım" in err


def test_gecerli_pdf():
    text, err = validate_pdf(CV)
    assert err is None and "Furkan Kaya" in text and "Python" in text
