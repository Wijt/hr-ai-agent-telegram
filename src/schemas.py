from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Proficiency = Literal["Native", "Fluent", "Advanced", "Intermediate", "Beginner"]


class PersonalInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(description="Ad soyad")
    title: Optional[str] = Field(description="Unvan / Rol")
    email: Optional[str] = Field(description="E-posta adresi")
    phone: Optional[str] = Field(description="Telefon numarası")
    location: Optional[str] = Field(description="Konum (Şehir, Ülke)")
    links: List[str] = Field(description="Profil bağlantıları (LinkedIn, GitHub vb.)")


class WorkExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: Optional[str] = Field(description="Şirket adı")
    position: Optional[str] = Field(description="Pozisyon / Unvan")
    start_date: Optional[str] = Field(description="Başlangıç tarihi (YYYY-MM)")
    end_date: Optional[str] = Field(description="Bitiş tarihi (YYYY-MM veya Present)")
    description: Optional[str] = Field(description="Sorumluluklar ve detaylar")
    technologies: List[str] = Field(description="Kullanılan temel teknolojiler")


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: Optional[str] = Field(description="Okul / Üniversite adı")
    degree: Optional[str] = Field(description="Derece (Lisans, Yüksek Lisans vb.)")
    field_of_study: Optional[str] = Field(description="Bölüm")
    end_date: Optional[str] = Field(description="Mezuniyet tarihi veya durumu (YYYY-MM)")


class LanguageSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(description="Dil adı")
    proficiency: Optional[Proficiency] = Field(description="Seviye")


class NormalizedCV(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personal_info: PersonalInfo
    summary: Optional[str] = Field(description="Kısa özet / Ön yazı")
    work_experience: List[WorkExperience]
    education: List[Education]
    skills: List[str] = Field(description="Teknik ve mesleki yeteneklerin listesi")
    languages: List[LanguageSkill]


class CVIntake(BaseModel):
    """cv_filer_agent'ın CV işleme adımının output_schema'sı: doğrulama + normalize edilmiş
    CV + knowledgebase'de bulunan olası duplicate bir arada."""

    model_config = ConfigDict(extra="forbid")

    is_cv: bool = Field(description="Belge gerçekten bir özgeçmiş mi")
    injection_detected: bool = Field(
        description="Belge içine talimat enjeksiyonu / prompt injection girişimi var mı"
    )
    reason: Optional[str] = Field(description="is_cv veya injection_detected kararının kısa gerekçesi")
    cv: Optional[NormalizedCV] = Field(
        description="is_cv=true ise çıkarılan normalize veri, değilse null"
    )
    existing_candidate_id: Optional[str] = Field(
        description=(
            "is_cv=true ise: knowledgebase'i tarayıp bu CV'nin email'iyle eşleşen bir aday "
            "bulunduysa o adayın candidate_id'si (klasör adı), bulunamadıysa null."
        )
    )


class SWOTAnalysis(BaseModel):
    """Bir adayın normalize edilmiş CV verisine dayanan SWOT analizi."""

    model_config = ConfigDict(extra="forbid")

    strengths: List[str] = Field(description="Adayın CV'ye dayanan güçlü yönleri (2-5 madde)")
    weaknesses: List[str] = Field(description="Gelişime açık / zayıf yönler (2-5 madde)")
    opportunities: List[str] = Field(
        description="Bu profile uygun fırsatlar / rol önerileri (2-5 madde)"
    )
    threats: List[str] = Field(
        description="Riskler / rekabet faktörleri, ör. eksik sertifika, dar teknoloji "
        "yelpazesi (2-5 madde)"
    )
