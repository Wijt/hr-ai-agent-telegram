from agno.agent import Agent
from agno.workflow import Parallel, Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from candidate_store import CandidateDocument
from model_factory import get_model
from models import BatchAnalysisResult, CandidateScore, CriterionScores, SingleAnalysisResult

_TOP_N = 3

# AGENTS.md §5 — evaluate_candidates'tan, sadece 1 profil bulunduğunda çağrılır.
analysis_agent = Agent(
    name="Analysis Agent",
    model=get_model(),
    instructions=(
        "Bir İK uzmanı gibi davran. Sana verilen aday profilini SADECE verilen "
        "kriterlere göre değerlendir, kriter dışı özellikleri yorumlama. Güçlü ve "
        "zayıf yönleri, somut gelişim tavsiyelerini Türkçe, okunaklı bir Markdown "
        "raporu (markdown_report) olarak üret."
    ),
    output_schema=SingleAnalysisResult,
)

# AGENTS.md §6 — evaluate_candidates'tan, N > 1 profil bulunduğunda, her aday için
# ayrı bir Parallel dalında çağrılır. averageScore/rank burada üretilmez, Python'da
# (LLM'siz) hesaplanır.
scoring_agent = Agent(
    name="Scoring Agent",
    model=get_model(),
    instructions=(
        "Bir İK uzmanı gibi davran. Sana verilen aday profilini, verilen her kritere "
        "göre AYRI AYRI 0-100 arası puanla (dynamic_scores). Her kriter için değil, "
        "adayın genel uyumu için kısa, tek cümlelik bir gerekçe (hr_evaluation) yaz."
    ),
    output_schema=CriterionScores,
)


async def analyze_single(document: CandidateDocument, criteria: list[str]) -> str:
    """Tekli değerlendirme — nitel Markdown rapor."""
    prompt = f"Aday profili:\n{document.markdown}\n\nKriterler: {', '.join(criteria)}"
    sonuc = await analysis_agent.arun(prompt)
    rapor: SingleAnalysisResult = sonuc.content
    return rapor.markdown_report


def _score_step(name: str, document: CandidateDocument, criteria: list[str]) -> Step:
    """Her Parallel dalı kendi aday dokümanını closure ile taşır — 'bir fonksiyon
    için class' yerine düz bir iç içe fonksiyon."""

    async def score(step_input: StepInput) -> StepOutput:
        prompt = f"Aday profili:\n{document.markdown}\n\nKriterler: {', '.join(criteria)}"
        sonuc = await scoring_agent.arun(prompt)
        scores: CriterionScores = sonuc.content
        return StepOutput(content={"document": document, "scores": scores})

    return Step(name=name, executor=score)


def _rank_step(step_names: list[str], criteria: list[str], processed_count: int) -> Step:
    """`Parallel` bloğunun ardından `previous_step_content` sadece SON dalın
    çıktısını taşıyor (elle doğrulandı) — bu yüzden her dalın sonucuna
    `step_input.get_step_content(isim)` ile, isim isim erişiyoruz."""

    def rank(step_input: StepInput) -> StepOutput:
        candidates: list[CandidateScore] = []
        for name in step_names:
            result = step_input.get_step_content(name)
            if not result:
                continue
            document: CandidateDocument = result["document"]
            scores: CriterionScores = result["scores"]
            values = list(scores.dynamic_scores.values())
            average = round(sum(values) / len(values), 2) if values else 0.0
            candidates.append(
                CandidateScore(
                    rank=0,
                    candidate_name=document.name,
                    pdf_file_name=document.source_filename,
                    dynamic_scores=scores.dynamic_scores,
                    average_score=average,
                    hr_evaluation=scores.hr_evaluation,
                )
            )

        candidates.sort(key=lambda c: c.average_score, reverse=True)
        top = candidates[:_TOP_N]
        for i, candidate in enumerate(top, start=1):
            candidate.rank = i

        result = BatchAnalysisResult(
            processed_cv_count=processed_count,
            user_defined_criteria=criteria,
            top_candidates=top,
        )
        return StepOutput(content=result)

    return Step(name="rank_top3", executor=rank)


async def analyze_batch(documents: list[CandidateDocument], criteria: list[str]) -> str:
    """Çoklu değerlendirme — her aday için ayrı bir Parallel dalı scoring_agent'ı
    aynı anda çalıştırır, sonra deterministik rank adımı ortalama+sıralamayı
    hesaplar. Burada Workflow/Parallel gerçekten gerekli: N adayın eşzamanlı
    işlenmesi elle asyncio.gather yazmak yerine Agno'nun kendi mekanizmasıyla."""
    step_names = [f"score_{i}" for i in range(len(documents))]
    branches = [
        _score_step(name, document, criteria) for name, document in zip(step_names, documents)
    ]

    workflow = Workflow(
        name="Batch Scoring",
        steps=[
            Parallel(*branches, name="score_all"),
            _rank_step(step_names, criteria, len(documents)),
        ],
    )
    sonuc = await workflow.arun(input="")
    result: BatchAnalysisResult = sonuc.content
    return result.model_dump_json(by_alias=True, indent=2)
