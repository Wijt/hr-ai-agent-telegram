from io import BytesIO

from pypdf import PdfReader
from pypdf._encryption import PasswordType
from pypdf.errors import PdfReadError, PdfStreamError

from models import PdfValidationResult, PdfValidationStatus

_MIN_TEXT_LENGTH = 50
_PDF_MAGIC = b"%PDF-"


def validate(content: bytes) -> PdfValidationResult:
    """ARCHITECTURE.md §8 — 6 kontrollü, LLM'siz doğrulama zinciri. İlk başarısız
    kontrolde durur. Dosya uzantısına hiç güvenilmez, sadece içerik kontrol edilir.
    """
    if len(content) == 0:
        return PdfValidationResult(
            status=PdfValidationStatus.EMPTY_FILE,
            user_message="Gönderdiğin dosya boş görünüyor.",
        )

    if not content.startswith(_PDF_MAGIC):
        return PdfValidationResult(
            status=PdfValidationStatus.NOT_A_PDF,
            user_message="Bu dosya bir PDF değil gibi görünüyor. Lütfen CV'ni PDF formatında gönder.",
        )

    try:
        reader = PdfReader(BytesIO(content))
    except (PdfReadError, PdfStreamError):
        return PdfValidationResult(
            status=PdfValidationStatus.CORRUPTED,
            user_message="PDF dosyası bozuk görünüyor, açamadım.",
        )

    if reader.is_encrypted:
        try:
            password_result = reader.decrypt("")
        except Exception:
            password_result = PasswordType.NOT_DECRYPTED
        if password_result == PasswordType.NOT_DECRYPTED:
            return PdfValidationResult(
                status=PdfValidationStatus.ENCRYPTED,
                user_message="Bu PDF şifre korumalı, açamıyorum. Şifresiz bir kopya gönderir misin?",
            )

    try:
        page_count = len(reader.pages)
    except (PdfReadError, PdfStreamError):
        return PdfValidationResult(
            status=PdfValidationStatus.CORRUPTED,
            user_message="PDF dosyası bozuk görünüyor, açamadım.",
        )

    if page_count == 0:
        return PdfValidationResult(
            status=PdfValidationStatus.EMPTY_PDF,
            user_message="Bu PDF'in içinde hiç sayfa yok.",
        )

    try:
        text = "".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, PdfStreamError):
        return PdfValidationResult(
            status=PdfValidationStatus.CORRUPTED,
            user_message="PDF dosyası bozuk görünüyor, açamadım.",
        )

    if len(text.strip()) < _MIN_TEXT_LENGTH:
        return PdfValidationResult(
            status=PdfValidationStatus.NO_EXTRACTABLE_TEXT,
            user_message=(
                "Bu PDF'ten metin çıkaramadım (muhtemelen taranmış görüntü). "
                "Şu an yalnızca metin tabanlı PDF'leri işleyebiliyorum."
            ),
        )

    return PdfValidationResult(status=PdfValidationStatus.VALID, extracted_text=text)
