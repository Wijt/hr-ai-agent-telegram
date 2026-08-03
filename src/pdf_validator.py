"""PDF doğrulama + metin çıkarımı — LLM'siz, deterministik (ARCHITECTURE.md §9).

`cv_processing_workflow`'un ilk adımı çağırır: geçersiz dosyada, hiçbir LLM
çağrısı yapılmadan kullanıcıya iletilecek Türkçe hata mesajı üretilir.
"""

from io import BytesIO

from pypdf import PasswordType, PdfReader
from pypdf.errors import DependencyError, PyPdfError

# Tüm sayfaların birleşik metni bundan kısaysa CV olarak işlenemez
# (taranmış görüntü PDF'leri tipik olarak 0 karakter döndürür).
_MIN_TEXT = 50


def validate_pdf(content: bytes) -> tuple[str | None, str | None]:
    """(metin, hata) döner — tam olarak biri dolu.

    Kontroller §9 tablosundaki sırayla, ilk hata durdurur. Dosya uzantısına
    güvenilmez: PDF'liği ilk 5 bayttaki %PDF- imzası belirler.
    """
    if not content:
        return None, "Gönderdiğin dosya boş görünüyor."

    if not content.startswith(b"%PDF-"):
        return None, "Bu dosya bir PDF değil gibi görünüyor. Lütfen CV'ni PDF formatında gönder."

    try:
        reader = PdfReader(BytesIO(content))
        # Boş parolayla açılabilenler (yalnızca owner-password'lu) şifreli sayılmaz.
        if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
            return None, "Bu PDF şifre korumalı, açamıyorum. Şifresiz bir kopya gönderir misin?"
        if len(reader.pages) == 0:
            return None, "Bu PDF'in içinde hiç sayfa yok."
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except DependencyError:
        # Desteklenmeyen şifreleme algoritması — kullanıcı için sonuç aynı.
        return None, "Bu PDF şifre korumalı, açamıyorum. Şifresiz bir kopya gönderir misin?"
    except PyPdfError:
        return None, "PDF dosyası bozuk görünüyor, açamadım."

    if len(text.strip()) < _MIN_TEXT:
        return None, (
            "Bu PDF'ten metin çıkaramadım (muhtemelen taranmış görüntü). "
            "Şu an yalnızca metin tabanlı PDF'leri işleyebiliyorum."
        )

    return text, None
