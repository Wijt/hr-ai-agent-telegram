"""Kayıtlı adaylar üzerinde analiz (ör. SWOT) üreten tool'lar.

Alım hattından (cv_intake.py) ayrı tutuluyor: burası sorgu zamanında, zaten
knowledgebase'de duran adaylar üzerinde çalışıyor, dosya kaydetme işiyle ilgisi yok.
"""

from agno.agent import Agent

from cv_intake import KNOWLEDGE_DIR
from models.model_factory import get_model
from schemas import SWOTAnalysis

swot_agent = Agent(
    name="CV SWOT Analyst",
    model=get_model(),
    instructions=(
        "Sana bir adayın normalize edilmiş CV verisi (JSON) verilecek. Bu veriye dayanarak "
        "objektif bir SWOT analizi yap: strengths (güçlü yönler), weaknesses (gelişime açık "
        "yönler), opportunities (bu profile uygun fırsatlar/roller), threats (riskler, ör. "
        "eksik sertifika, dar teknoloji yelpazesi, deneyim boşlukları). Her kategori için "
        "2-5 madde yaz, kısa ve somut olsun, CV'deki gerçek bilgilere dayansın, uydurma yapma."
    ),
    output_schema=SWOTAnalysis,
)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (belirtilmedi)"


async def analyze_cv_swot(candidate_id: str) -> str:
    """Kayıtlı bir adayın CV'sine dayanan SWOT analizi (güçlü/zayıf yönler, fırsatlar,
    tehditler) üretir. Kullanıcı bir adayın SWOT analizini istediğinde çağır.

    Args:
        candidate_id: Analiz edilecek adayın candidate_id'si (klasör adı, ör. 'furkan_kaya').
            Önce list_files/grep_file ile doğru candidate_id'yi bul.
    """
    normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
    if not normalized_path.exists():
        return f"'{candidate_id}' adında kayıtlı bir aday bulunamadı."

    cv_json = normalized_path.read_text(encoding="utf-8")
    run_output = await swot_agent.arun(input=cv_json)
    analysis = run_output.content
    if not isinstance(analysis, SWOTAnalysis):
        return "SWOT analizi üretilemedi."

    return (
        f"**SWOT Analizi — {candidate_id}**\n\n"
        f"**Güçlü Yönler**\n{_bullets(analysis.strengths)}\n\n"
        f"**Zayıf Yönler**\n{_bullets(analysis.weaknesses)}\n\n"
        f"**Fırsatlar**\n{_bullets(analysis.opportunities)}\n\n"
        f"**Tehditler**\n{_bullets(analysis.threats)}"
    )
