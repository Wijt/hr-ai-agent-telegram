"""SWOT analizi tool'u. YAPILANDIRILMIŞ VERİ (JSON) döner, hazır mesaj değil —
kullanıcıya nasıl sunulacağına çağıran chat agent karar verir (bkz. main.py'deki
instructions). Böylece agent sonucu isteğe uyarlayabiliyor ("kısa tut", "sadece riskleri
söyle"); hazır markdown döndüğünde bu mümkün değildi.
"""

import json

from agno.agent import Agent

from utils.model_factory import get_model
from schemas import SWOTAnalysis
from utils.candidate_store import candidate_full_name, normalized_json_path

# Bu tool'a özgü analiz agent'ı.
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


async def analyze_cv_swot(candidate_id: str) -> str:
    """Kayıtlı bir adayın CV'sine dayanan SWOT analizi (güçlü/zayıf yönler, fırsatlar,
    tehditler) üretir. YAPILANDIRILMIŞ VERİ (JSON) döner — hazır bir mesaj DEĞİLDİR;
    sonucu okunaklı bir markdown'a çevirip kullanıcıya sunmak çağıran agent'ın işidir,
    ham JSON'u kullanıcıya gösterme.

    Args:
        candidate_id: Analiz edilecek adayın candidate_id'si (klasör adı, ör. 'furkan_kaya').
    """
    normalized_path = normalized_json_path(candidate_id)
    if not normalized_path.exists():
        return json.dumps(
            {"status": "error", "message": f"'{candidate_id}' adında kayıtlı bir aday bulunamadı."},
            ensure_ascii=False,
        )

    cv_json = normalized_path.read_text(encoding="utf-8")
    run_output = await swot_agent.arun(input=cv_json)
    analysis = run_output.content
    if not isinstance(analysis, SWOTAnalysis):
        return json.dumps(
            {"status": "error", "message": "SWOT analizi üretilemedi."}, ensure_ascii=False
        )

    cv_data = json.loads(cv_json)

    return json.dumps(
        {
            "status": "success",
            "candidate_id": candidate_id,
            "candidate_name": candidate_full_name(cv_data, candidate_id),
            **analysis.model_dump(),
        },
        ensure_ascii=False,
        indent=2,
    )
