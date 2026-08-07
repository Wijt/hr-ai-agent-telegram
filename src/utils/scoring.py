"""İki skorlama tool'unun (score_cv_against_criteria, score_multiple_candidates) ortak
puanlama çekirdeği: scoring_agent ve tek adayı puanlayan score_candidate.
"""

import json
from typing import Optional

from agno.agent import Agent

from utils.model_factory import get_model
from schemas import CandidateScoreReport
from utils.candidate_store import candidate_full_name, normalized_json_path

scoring_agent = Agent(
    name="CV Criteria Scorer",
    model=get_model(),
    instructions=(
        "Sana bir adayın normalize edilmiş CV verisi (JSON) ve kullanıcının belirlediği "
        "değerlendirme kriterleri verilecek. Her kriter için 0-100 arası bir puan ver "
        "(kısa bir gerekçeyle) — kriterle ilgili veri yoksa düşük puan ver ve gerekçede "
        "bunu belirt, uydurma yapma. Ardından bu kriterlere göre genel güçlü yönler, "
        "zayıf yönler ve gelişim tavsiyeleri yaz. Son olarak tek cümlelik bir İK "
        "değerlendirmesi yaz. Sadece CV'deki gerçek bilgilere dayan."
    ),
    output_schema=CandidateScoreReport,
)


async def score_candidate(candidate_id: str, criteria: list[str]) -> Optional[dict]:
    """Tek bir adayı verilen kriterlere göre puanlar; hem score_cv_against_criteria hem
    score_multiple_candidates bu ortak mantığı kullanır. Aday yoksa None döner.
    """
    normalized_path = normalized_json_path(candidate_id)
    if not normalized_path.exists():
        return None

    cv_json = normalized_path.read_text(encoding="utf-8")
    criteria_listing = "\n".join(f"- {c}" for c in criteria)
    prompt = f"Değerlendirme kriterleri:\n{criteria_listing}\n\nCV verisi (JSON):\n{cv_json}"

    run_output = await scoring_agent.arun(input=prompt)
    report = run_output.content
    if not isinstance(report, CandidateScoreReport) or not report.scores:
        return None

    # Ortalamayı LLM'e hesaplatmıyoruz — LLM'ler aritmetikte güvenilmez, bu deterministik.
    average_score = round(sum(s.score for s in report.scores) / len(report.scores), 1)
    cv_data = json.loads(cv_json)

    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_full_name(cv_data, candidate_id),
        "scores": {s.criterion: s.score for s in report.scores},
        "average_score": average_score,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "development_suggestions": report.development_suggestions,
        "hr_evaluation": report.hr_evaluation,
    }
