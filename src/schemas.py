"""LLM çıktı şemaları (ARCHITECTURE.md §7). Pydantic olmaları Agno'nun
`output_schema` gereksinimi. Alan açıklamaları LLM'e gider — Türkçe ve net.
"""

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """LLM Extraction'ın ortak şeması: her formattaki CV buna normalize edilir."""

    full_name: str | None = Field(
        default=None, description="Adayın tam adı. CV'de açıkça yazmıyorsa null bırak, tahmin etme."
    )
    skills: list[str] = Field(
        default_factory=list, description="Teknik/mesleki beceriler (ör. 'Python', 'proje yönetimi')."
    )
    work_experience: list[str] = Field(
        default_factory=list,
        description="Her deneyim tek satır: 'rol — şirket (süre): kısa açıklama'. Sadece CV'de yazanlar.",
    )
    languages: list[str] = Field(
        default_factory=list, description="Diller, varsa seviyesiyle (ör. 'İngilizce (C1)')."
    )
    education: list[str] = Field(
        default_factory=list, description="Eğitim, her kayıt tek satır: 'derece — kurum (yıl)'."
    )


class SingleAnalysisResult(BaseModel):
    """Tekli CV analizinin çıktısı — markdown_report Telegram'a birebir gönderilir."""

    candidate_name: str = Field(description="Adayın adı; profilde yoksa 'Aday' yaz.")
    strengths: list[str] = Field(description="Kullanıcının kriterlerine göre güçlü yönler.")
    weaknesses: list[str] = Field(description="Aynı kriterlere göre zayıf/eksik yönler.")
    recommendations: list[str] = Field(description="Somut gelişim tavsiyeleri.")
    markdown_report: str = Field(
        description="Tüm bulguları içeren Türkçe Markdown raporu — kısa başlıklar ve madde işaretleri."
    )
