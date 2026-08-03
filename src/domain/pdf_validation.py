"""PDF doğrulama sonucunun tipli karşılığı (ARCHITECTURE.md §7, §9).

LLM içermez — `services.pdf_validator.PdfValidator` üretir,
`cv_processing_workflow`'un `validate_pdf` adımı tüketir.
"""

from enum import Enum

from pydantic import BaseModel


class PdfValidationStatus(str, Enum):
    """§9 tablosundaki durum kodları — ilk başarısız kontrol hangi koddaysa o döner."""

    EMPTY_FILE = "EMPTY_FILE"
    NOT_A_PDF = "NOT_A_PDF"
    ENCRYPTED = "ENCRYPTED"
    CORRUPTED = "CORRUPTED"
    EMPTY_PDF = "EMPTY_PDF"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
    VALID = "VALID"


class PdfValidationResult(BaseModel):
    status: PdfValidationStatus
    extracted_text: str | None = None  # sadece status == VALID iken dolu
    user_message: str | None = None  # sadece status != VALID iken dolu, Telegram'a birebir gönderilir

    @property
    def is_valid(self) -> bool:
        return self.status is PdfValidationStatus.VALID
