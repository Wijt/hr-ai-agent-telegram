"""Kayıtlı adaylar üzerinde analiz (ör. SWOT, kriter bazlı puanlama) üreten tool'lar.

Alım hattından (cv_intake.py) ayrı tutuluyor: burası sorgu zamanında, zaten
knowledgebase'de duran adaylar üzerinde çalışıyor, dosya kaydetme işiyle ilgisi yok.

Buradaki tool'ların HEPSİ aynı prensibi izler: YAPILANDIRILMIŞ VERİ (JSON) döner, hazır
mesaj değil — kullanıcıya nasıl sunulacağına çağıran chat agent karar verir (bkz. main.py'deki
instructions). Böylece agent sonucu isteğe uyarlayabiliyor ("kısa tut", "sadece riskleri
söyle", skorlamayla birlikte özetle); hazır markdown döndüğünde bu mümkün değildi.
"""

import asyncio
import json
from typing import Optional

from agno.agent import Agent

from cv_intake import KNOWLEDGE_DIR
from models.model_factory import get_model
from schemas import CandidateScoreReport, SWOTAnalysis

swot_agent = Agent(
    name="CV SWOT Analyst",
    model=get_model(),
    instructions="""# TASK
You get the normalized CV data of one candidate in JSON.
Write an objective SWOT analysis from this data.

# FIELDS
- strengths: the strong points of the candidate.
- weaknesses: the points that need development.
- opportunities: the roles and the openings that match this profile.
- threats: the risks, such as an absent certificate, a narrow range of technologies,
  or a gap in the work history.

# RULES
Write 2 to 5 items for each field.
Keep each item short and concrete.
Use only the facts in the CV. Never invent a fact.
Write every item in Turkish.
""",
    output_schema=SWOTAnalysis,
)


async def analyze_cv_swot(candidate_id: str) -> str:
    """Make a SWOT analysis of a saved candidate from the CV data of that candidate.

    The tool returns structured data. It does not return a ready message. Write the
    Turkish markdown message yourself. Never show the raw JSON to the user.

    Args:
        candidate_id: The candidate_id of the candidate. This is the folder name, for
            example 'furkan_kaya'.
    """
    normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
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
    candidate_name = (cv_data.get("personal_info") or {}).get("full_name") or candidate_id

    return json.dumps(
        {
            "status": "success",
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            **analysis.model_dump(),
        },
        ensure_ascii=False,
        indent=2,
    )


scoring_agent = Agent(
    name="CV Criteria Scorer",
    model=get_model(),
    instructions="""# TASK
You get the evaluation criteria of the user.
You also get the normalized CV data of one candidate in JSON.
Score the candidate against each criterion.

# RULES
Give a score from 0 to 100 for each criterion.
Write a one-sentence justification for each score.
If the CV holds no data for a criterion, give a low score. Write this fact in the
justification. Never invent a fact.
Then write the strengths, the weaknesses, and the development suggestions for these criteria.
Then write the HR evaluation in one sentence.
Use only the facts in the CV.
Write every item in Turkish.
""",
    output_schema=CandidateScoreReport,
)


async def _score_candidate(candidate_id: str, criteria: list[str]) -> Optional[dict]:
    """Tek bir adayı verilen kriterlere göre puanlar; hem score_cv_against_criteria hem
    score_multiple_candidates bu ortak mantığı kullanır. Aday yoksa None döner.
    """
    normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
    if not normalized_path.exists():
        return None

    cv_json = normalized_path.read_text(encoding="utf-8")
    criteria_listing = "\n".join(f"- {c}" for c in criteria)
    prompt = f"Evaluation criteria:\n{criteria_listing}\n\nCV data (JSON):\n{cv_json}"

    run_output = await scoring_agent.arun(input=prompt)
    report = run_output.content
    if not isinstance(report, CandidateScoreReport) or not report.scores:
        return None

    # Ortalamayı LLM'e hesaplatmıyoruz — LLM'ler aritmetikte güvenilmez, bu deterministik.
    average_score = round(sum(s.score for s in report.scores) / len(report.scores), 1)
    cv_data = json.loads(cv_json)
    candidate_name = (cv_data.get("personal_info") or {}).get("full_name") or candidate_id

    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "scores": {s.criterion: s.score for s in report.scores},
        "average_score": average_score,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "development_suggestions": report.development_suggestions,
        "hr_evaluation": report.hr_evaluation,
    }


async def score_cv_against_criteria(candidate_id: str, criteria: list[str]) -> str:
    """Score one candidate against the evaluation criteria of the user.

    The tool returns structured data. It does not return a ready message. Write the
    Turkish markdown message yourself. Never show the raw JSON to the user.

    Args:
        candidate_id: The candidate_id of the candidate to score.
        criteria: The evaluation criteria of the user. For example:
            ["React tecrübesi", "Clean Code", "Uzaktan çalışma uyumu"].
    """
    result = await _score_candidate(candidate_id, criteria)
    if result is None:
        return json.dumps(
            {"status": "error", "message": f"'{candidate_id}' adında kayıtlı bir aday bulunamadı."},
            ensure_ascii=False,
        )
    return json.dumps({"status": "success", **result}, ensure_ascii=False, indent=2)


async def score_multiple_candidates(candidate_ids: list[str], criteria: list[str]) -> str:
    """Score two or more candidates against the same criteria and rank them.

    The tool returns the three candidates with the highest average score.
    The tool returns structured data. It does not return a ready message. Write the
    ranked Turkish markdown list yourself. Never show the raw JSON to the user.

    Args:
        candidate_ids: The candidate_id values of the candidates to score.
        criteria: The evaluation criteria of the user.
    """
    results = await asyncio.gather(*(_score_candidate(cid, criteria) for cid in candidate_ids))
    valid_results = [r for r in results if r is not None]
    valid_results.sort(key=lambda r: r["average_score"], reverse=True)
    top = valid_results[:3]

    top_candidates = [
        {
            "rank": i + 1,
            "candidateId": r["candidate_id"],
            "candidateName": r["candidate_name"],
            "dynamicScores": r["scores"],
            "averageScore": r["average_score"],
            "hrEvaluation": r["hr_evaluation"],
        }
        for i, r in enumerate(top)
    ]

    return json.dumps(
        {
            "status": "success",
            "processedCVCount": len(valid_results),
            "userDefinedCriteria": criteria,
            "topCandidates": top_candidates,
        },
        ensure_ascii=False,
        indent=2,
    )


def summarize_candidates(candidate_ids: list[str]) -> str:
    """Return short identity data for each candidate_id: name, title, and latest company.

    The tool does not return the full CV. The tool reads a few fields from disk and
    calls no model. The tool is much cheaper than get_file.
    If one name matches more than one record, call this tool first. Then ask the user
    which record is correct with this data. Never ask an empty question.

    Args:
        candidate_ids: The candidate_id values to compare.
    """
    summaries = []
    for candidate_id in candidate_ids:
        normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
        if not normalized_path.exists():
            continue
        data = json.loads(normalized_path.read_text(encoding="utf-8"))
        personal = data.get("personal_info") or {}
        work_experience = data.get("work_experience") or []
        latest_company = work_experience[0].get("company") if work_experience else None
        summaries.append(
            {
                "candidateId": candidate_id,
                "fullName": personal.get("full_name"),
                "title": personal.get("title"),
                "latestCompany": latest_company,
            }
        )
    return json.dumps(summaries, ensure_ascii=False, indent=2)
