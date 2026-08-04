from agno.agent import Agent
from agno.media import File

import pdf_validator
from model_factory import get_model
from models import CandidateProfile, PdfValidationStatus

# AGENTS.md §4 — intake sürecinin LLM adımı. process_cv içinden çağrılır, Router
# tarafından seçilmez.
extraction_agent = Agent(
    name="Extraction Agent",
    model=get_model(),
    instructions=(
        "Sana verilen ham CV metninden yalnızca açıkça belirtilmiş bilgileri çıkar. "
        "Emin olmadığın alanları boş bırak, uydurma. Toplam deneyim yılı metinde "
        "açıkça yazmıyorsa iş deneyimi tarihlerinden makul şekilde hesaplayabilirsin, "
        "aksi halde boş bırak."
    ),
    output_schema=CandidateProfile,
)


async def process_cv(file: File) -> tuple[CandidateProfile | None, str | None]:
    """Intake süreci: doğrula -> LLM extraction -> normalize.

    İki sabit adım, hep aynı sırada, tek bir erken-çıkış koşuluyla — bunun için
    Agno Workflow'a gerek yok, düz bir if/return yeterli (bkz. Parallel'in
    genuinely gerekli olduğu candidate_analysis.py ile karşılaştır).

    Döner: (profile, None) başarılıysa; (None, hata_mesajı) geçersiz PDF'te —
    ARCHITECTURE.md'nin "tuple/string dön" ilkesi, isinstance ile tahmin yürütmek
    yerine.
    """
    sonuc = pdf_validator.validate(file.content)
    if sonuc.status != PdfValidationStatus.VALID:
        return None, sonuc.user_message

    run = await extraction_agent.arun(sonuc.extracted_text)
    return run.content, None
