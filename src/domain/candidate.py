"""Aday veri modelleri (ARCHITECTURE.md §7).

`CandidateProfile` — LLM Extraction'ın ortak çıktı şeması: farklı formatlardaki
CV'ler bu tek şemaya normalize edilir (ödevin "LLM Extraction → ortak JSON" gereksinimi).
`SingleAnalysisResult` — tekli modda Analysis Agent'ın nitel rapor şeması.

Alan açıklamaları (description) bilinçli olarak Türkçe ve ayrıntılı: `output_schema`
olarak LLM'e gidiyorlar, extraction/analiz kalitesini doğrudan etkiliyorlar.
"""

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """Ham CV metninden çıkarılan, formattan bağımsız ortak aday profili."""

    full_name: str | None = Field(
        default=None,
        description="Adayın tam adı. CV metninde açıkça yazmıyorsa null bırak, tahmin etme.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Teknik ve mesleki beceriler (ör. 'Python', 'React', 'proje yönetimi').",
    )
    work_experience: list[str] = Field(
        default_factory=list,
        description=(
            "Her iş deneyimi tek satırlık özet: 'rol — şirket (süre): kısa açıklama'. "
            "Sadece CV'de açıkça yazan deneyimleri listele."
        ),
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Konuşulan diller, varsa seviyesiyle (ör. 'İngilizce (C1)').",
    )
    education: list[str] = Field(
        default_factory=list,
        description="Eğitim geçmişi, her kayıt tek satır: 'derece — kurum (yıl)'.",
    )


class SingleAnalysisResult(BaseModel):
    """Tekli CV analizinin nitel çıktısı — `markdown_report` Telegram'a birebir gönderilir."""

    candidate_name: str = Field(
        description="Değerlendirilen adayın adı; profilde isim yoksa 'Aday' yaz."
    )
    strengths: list[str] = Field(
        description="Kullanıcının tanımladığı kriterlere göre güçlü yönler."
    )
    weaknesses: list[str] = Field(
        description="Aynı kriterlere göre zayıf/eksik yönler."
    )
    recommendations: list[str] = Field(
        description="Adaya yönelik somut gelişim tavsiyeleri."
    )
    markdown_report: str = Field(
        description=(
            "Yukarıdaki tüm bulguları içeren, Türkçe, okunaklı bir Markdown raporu. "
            "Telegram'a olduğu gibi gönderilecek — kısa başlıklar ve madde işaretleri kullan."
        )
    )
