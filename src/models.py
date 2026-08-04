from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PdfValidationStatus(str, Enum):
    VALID = "valid"
    EMPTY_FILE = "empty_file"
    NOT_A_PDF = "not_a_pdf"
    ENCRYPTED = "encrypted"
    CORRUPTED = "corrupted"
    EMPTY_PDF = "empty_pdf"
    NO_EXTRACTABLE_TEXT = "no_extractable_text"


class PdfValidationResult(BaseModel):
    """ARCHITECTURE.md §8 — 6 kontrollü doğrulama zincirinin tipli çıktısı."""

    status: PdfValidationStatus
    extracted_text: str | None = None
    user_message: str | None = None


class CandidateProfile(BaseModel):
    """LLM Extraction'ın ürettiği, farklı CV formatlarını normalize eden ortak şema.

    Kullanıcının paylaştığı zengin JSON şemasından KISS gereği seçilmiş bir alt
    küme: tüm alanlar düz (nested obje/enum yok) — hem extraction'ın hatasız
    dolmasını hem de Markdown'a render etmeyi basit tutuyor. `additional_info`,
    `projects`, `extraction_metadata` gibi ödevin çekirdek amacına (dinamik
    kritere göre değerlendirme) doğrudan hizmet etmeyen bölümler bilinçli olarak
    dışarıda bırakıldı.

    Her alanın `description`'ı extraction ajanına yön vermek için yazıldı (örnek
    değerler içerir); `json_schema_extra={"label": ...}` ise candidate_store.py
    içindeki render_candidate_markdown'ın kullandığı kısa Türkçe başlıktır — alan
    eklenip çıkarıldıkça render fonksiyonu değişmeden bu ikisi burada birlikte
    güncellenir.
    """

    full_name: str | None = Field(default=None, description="Adayın tam adı")
    title: str | None = Field(
        default=None,
        description="Unvan / mevcut rol, örn. 'Senior Backend Developer'",
        json_schema_extra={"label": "Unvan"},
    )
    email: str | None = Field(
        default=None, description="E-posta adresi", json_schema_extra={"label": "E-posta"}
    )
    phone: str | None = Field(
        default=None, description="Telefon numarası", json_schema_extra={"label": "Telefon"}
    )
    location: str | None = Field(
        default=None,
        description="Şehir/ülke, örn. 'İstanbul, Türkiye'",
        json_schema_extra={"label": "Konum"},
    )
    links: list[str] = Field(
        default_factory=list,
        description="GitHub, LinkedIn, portfolyo gibi bağlantılar (URL)",
        json_schema_extra={"label": "Bağlantılar"},
    )

    total_experience_years: float | None = Field(
        default=None,
        description="Toplam iş deneyimi (yıl), örn. 4.5",
        json_schema_extra={"label": "Toplam deneyim (yıl)"},
    )
    work_model: str | None = Field(
        default=None,
        description="Çalışma tercihi, örn. Remote, Hybrid, On-site, Flexible",
        json_schema_extra={"label": "Çalışma modeli"},
    )
    employment_type: str | None = Field(
        default=None,
        description="Çalışma biçimi, örn. Full-time, Part-time, Contractor, Freelance",
        json_schema_extra={"label": "Çalışma biçimi"},
    )
    notice_period: str | None = Field(
        default=None,
        description="İşe başlayabileceği süre, örn. 'Hemen', '1 ay'",
        json_schema_extra={"label": "İhbar süresi"},
    )
    military_status: str | None = Field(
        default=None,
        description="Askerlik durumu (belirtilmişse), örn. Yaptı, Muaf, Tecilli",
        json_schema_extra={"label": "Askerlik durumu"},
    )

    skills: list[str] = Field(
        default_factory=list,
        description="Teknik/mesleki beceriler",
        json_schema_extra={"label": "Beceriler"},
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="Sertifikalar",
        json_schema_extra={"label": "Sertifikalar"},
    )
    work_experience: list[str] = Field(
        default_factory=list,
        description="Her girdi: şirket, pozisyon, tarih aralığı ve kısa açıklama içeren tek özet cümle",
        json_schema_extra={"label": "İş Deneyimi"},
    )
    education: list[str] = Field(
        default_factory=list,
        description="Her girdi: okul, bölüm, derece ve tarih içeren tek özet cümle",
        json_schema_extra={"label": "Eğitim"},
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Örn. 'İngilizce (C1)', 'Almanca (A2)'",
        json_schema_extra={"label": "Diller"},
    )


class SingleAnalysisResult(BaseModel):
    """Tekli CV nitel analiz raporu (ödev §2)."""

    candidate_name: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    markdown_report: str = Field(description="Telegram'a doğrudan gönderilecek Markdown rapor")


class CriterionScores(BaseModel):
    """scoring_agent'ın ürettiği ham çıktı. averageScore/rank sonradan Python'da
    (LLM'e bırakılmadan) hesaplanır — bkz. ARCHITECTURE.md §6 madde 5."""

    dynamic_scores: dict[str, int] = Field(description="Her kritere 0-100 arası puan")
    hr_evaluation: str = Field(description="Kısa değerlendirme gerekçesi")

    @field_validator("dynamic_scores")
    @classmethod
    def clamp_scores(cls, v: dict[str, int]) -> dict[str, int]:
        return {k: max(0, min(100, val)) for k, val in v.items()}


class CandidateScore(BaseModel):
    """Ödev dokümanındaki JSON şemasına birebir uyan tek aday kaydı."""

    model_config = ConfigDict(populate_by_name=True)

    rank: int
    candidate_name: str = Field(alias="candidateName")
    pdf_file_name: str = Field(alias="pdfFileName")
    dynamic_scores: dict[str, int] = Field(alias="dynamicScores")
    average_score: float = Field(alias="averageScore")
    hr_evaluation: str = Field(alias="hrEvaluation")


class BatchAnalysisResult(BaseModel):
    """Ödev dokümanındaki (§4) çoklu CV JSON çıktı formatı."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = "success"
    processed_cv_count: int = Field(alias="processedCVCount")
    user_defined_criteria: list[str] = Field(alias="userDefinedCriteria")
    top_candidates: list[CandidateScore] = Field(alias="topCandidates")
