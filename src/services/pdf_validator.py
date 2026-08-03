"""LLM'siz, deterministik PDF doğrulama + metin çıkarımı (ARCHITECTURE.md §9).

`cv_processing_workflow`'un ilk adımı (`validate_pdf`) tarafından sarmalanır;
extraction'dan — dolayısıyla her türlü LLM çağrısından — önce çalışır. Geçersiz
dosyalar için hiçbir API çağrısı yapılmaz.

Kontroller §9 tablosundaki sırayla uygulanır, ilk başarısız kontrolde durulur.
"""

from io import BytesIO

from pypdf import PasswordType, PdfReader
from pypdf.errors import PyPdfError

from domain.pdf_validation import PdfValidationResult, PdfValidationStatus

_PDF_MAGIC = b"%PDF-"
# Tüm sayfaların birleşik metni bundan kısaysa CV olarak işlenemez (taranmış
# görüntü PDF'leri tipik olarak 0 karakter döndürür; 50, boilerplate'i elemek
# için küçük bir güvenlik payı).
_MIN_TEXT_CHARS = 50

# Kullanıcıya dönen mesajlar — Telegram'a birebir gönderilir (§9 tablosu).
_USER_MESSAGES: dict[PdfValidationStatus, str] = {
    PdfValidationStatus.EMPTY_FILE: "Gönderdiğin dosya boş görünüyor.",
    PdfValidationStatus.NOT_A_PDF: (
        "Bu dosya bir PDF değil gibi görünüyor. Lütfen CV'ni PDF formatında gönder."
    ),
    PdfValidationStatus.ENCRYPTED: (
        "Bu PDF şifre korumalı, açamıyorum. Şifresiz bir kopya gönderir misin?"
    ),
    PdfValidationStatus.CORRUPTED: "PDF dosyası bozuk görünüyor, açamadım.",
    PdfValidationStatus.EMPTY_PDF: "Bu PDF'in içinde hiç sayfa yok.",
    PdfValidationStatus.NO_EXTRACTABLE_TEXT: (
        "Bu PDF'ten metin çıkaramadım (muhtemelen taranmış görüntü). "
        "Şu an yalnızca metin tabanlı PDF'leri işleyebiliyorum."
    ),
}


def _fail(status: PdfValidationStatus) -> PdfValidationResult:
    return PdfValidationResult(status=status, user_message=_USER_MESSAGES[status])


class PdfValidator:
    @staticmethod
    def validate(content: bytes, filename: str) -> PdfValidationResult:
        """`content`'i doğrular; geçerliyse çıkarılmış metni de döndürür.

        `filename` bilinçli olarak karara dahil edilmez: uzantıya güvenilmez
        (kullanıcı .jpg dosyasını cv.pdf diye gönderebilir), PDF'liği magic
        number belirler. İmzada tutulmasının nedeni loglama/ileriye dönük
        raporlamada dosya adının elde olması.
        """
        if len(content) == 0:
            return _fail(PdfValidationStatus.EMPTY_FILE)

        if not content.startswith(_PDF_MAGIC):
            return _fail(PdfValidationStatus.NOT_A_PDF)

        try:
            reader = PdfReader(BytesIO(content))

            if reader.is_encrypted:
                # §9: önce boş parolayla açmayı dene (bazı PDF'ler yalnızca
                # owner-password ile kısıtlanmıştır, boş user-password ile okunur).
                try:
                    decrypted = reader.decrypt("")
                except Exception:
                    # Desteklenmeyen şifreleme algoritması / eksik bağımlılık —
                    # kullanıcı açısından sonuç aynı: dosya açılamıyor.
                    return _fail(PdfValidationStatus.ENCRYPTED)
                if decrypted == PasswordType.NOT_DECRYPTED:
                    return _fail(PdfValidationStatus.ENCRYPTED)

            if len(reader.pages) == 0:
                return _fail(PdfValidationStatus.EMPTY_PDF)

            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except PyPdfError:
            return _fail(PdfValidationStatus.CORRUPTED)

        if len(text.strip()) < _MIN_TEXT_CHARS:
            return _fail(PdfValidationStatus.NO_EXTRACTABLE_TEXT)

        return PdfValidationResult(status=PdfValidationStatus.VALID, extracted_text=text)
