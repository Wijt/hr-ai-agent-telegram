"""Router Agent — Telegram'a bağlı tek ajan (AGENTS.md §1).

LLM'in tek görevi hangi tool'un çağrılacağını seçmek; iş mantığı tool'ların
içinde ("LLM router, kod garantör" — ARCHITECTURE.md §5).
"""

from typing import Optional, Sequence

from agno.agent import Agent
from agno.media import File
from agno.run import RunContext
from agno.run.agent import RunInput
from agno.tools import tool

from agents import analysis_agent
from model_factory import get_model
from schemas import CandidateProfile, SingleAnalysisResult
from workflows import cv_processing_workflow, stopped_early


def set_dynamic_criteria(run_context: RunContext, criteria: list[str]) -> str:
    """Kullanıcının CV değerlendirme kriterlerini kaydeder.

    Kullanıcı "X ve Y'ye göre skorla/değerlendir" gibi kriter tanımladığında çağır.
    criteria: her kriter ayrı bir madde olarak.
    """
    if run_context.session_state is None:
        run_context.session_state = {}
    run_context.session_state["dynamic_criteria"] = criteria
    return f"Kriterler kaydedildi: {', '.join(criteria)}"


@tool(stop_after_tool_call=True)  # dönüş LLM'e geri gitmez, olduğu gibi kullanıcıya iletilir
def submit_cv(
    run_context: RunContext,
    criteria: Optional[list[str]] = None,
    files: Optional[Sequence[File]] = None,  # o turun ekli dosyaları — Agno otomatik enjekte eder
) -> str:
    """Kullanıcının gönderdiği CV PDF'ini analiz eder. Bir belge geldiğinde her zaman çağır.

    criteria: kullanıcı aynı mesajda değerlendirme kriteri de yazdıysa buraya geçir
    (yazmadıysa boş bırak, kayıtlı kriterler kullanılır).
    """
    if not files:
        return "Analiz için bir PDF dosyası göndermelisin."

    if run_context.session_state is None:
        run_context.session_state = {}
    if criteria:  # dosyayla birlikte gelen kriter, kayıtlıyı günceller
        run_context.session_state["dynamic_criteria"] = criteria
    criteria = run_context.session_state.get("dynamic_criteria")
    if not criteria:
        return (
            "Bu CV'yi hangi kriterlere göre değerlendirmemi istersin? Önce kriterlerini "
            "yaz (örn. 'React tecrübesi ve temiz koda göre skorla'), sonra CV'yi yeniden gönder."
        )

    run = cv_processing_workflow.run(files=list(files))
    if stopped_early(run):
        return str(run.content)  # validate_pdf'in kullanıcı için hazırladığı hata mesajı

    profile = run.content
    if not isinstance(profile, CandidateProfile):  # extract adımı beklenmedik biçimde başarısız
        return f"CV işlenirken beklenmedik bir sorun oluştu: {profile}"

    analiz = analysis_agent.run(
        f"Aday profili (JSON):\n{profile.model_dump_json()}\n\nKriterler: {', '.join(criteria)}"
    )
    if isinstance(analiz.content, SingleAnalysisResult):
        return analiz.content.markdown_report
    return str(analiz.content)


def force_submit_cv_on_file(run_input: RunInput, agent: Agent) -> None:
    """Dosya ekli turda submit_cv çağrısı LLM kararına bırakılmaz (ARCHITECTURE.md §5).

    tool_choice Agent nesnesinde kalıcıdır — bu yüzden her turda açıkça set edilir
    ya da geri alınır. submit_cv'deki stop_after_tool_call=True, zorlanan tool'un
    aynı run içinde tekrar tekrar çağrılmasını (sonsuz döngü) engeller.
    """
    # Responses API biçimi (Chat Completions'taki {"function": {...}} sarmalayıcısı yok)
    agent.tool_choice = (
        {"type": "function", "name": "submit_cv"} if run_input.files else None
    )


chat_agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions=[
        "Sen samimi, kısa ve bağlamı koruyan bir Türkçe İK asistanısın.",
        "Kullanıcı puanlama/değerlendirme kriterleri tanımlıyorsa set_dynamic_criteria çağır.",
        "Kullanıcı bir PDF/CV gönderdiyse her zaman submit_cv çağır.",
        "CV içeriğini asla kendin yorumlama ya da skorlama — bu iş uzman ajanlara ait.",
    ],
    tools=[set_dynamic_criteria, submit_cv],
    pre_hooks=[force_submit_cv_on_file],
    session_state={"dynamic_criteria": None},  # yeni session'a deepcopy ile başlangıç değeri
    send_media_to_model=False,  # PDF baytları LLM'e gitmez (ARCHITECTURE.md §10.1)
    store_media=True,
    markdown=True,
    add_history_to_context=True,
)
