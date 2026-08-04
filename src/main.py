from pathlib import Path
from typing import Optional, Sequence

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.media import File
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram
from agno.run import RunContext
from agno.run.agent import RunInput
from agno.tools import tool

import candidate_analysis
import candidate_store
import cv_intake
from config import settings
from model_factory import get_model


def pre_hook(run_input: RunInput, agent: Agent) -> None:
    """AGENTS.md §1/§5 — dosya varsa submit_cv çağrılması LLM kararına değil koda
    bağlı: tool_choice her turda ya submit_cv'ye sabitlenir ya da 'auto'ya
    sıfırlanır (agent aynı nesne olduğu için önceki turdan kalmasın diye).
    Dict formatı OpenAI'nin kendi tool_choice API'sine birebir aktarılıyor
    (agno/models/openai/chat.py: request_params['tool_choice'] = tool_choice)."""
    if run_input.files:
        agent.tool_choice = {"type": "function", "function": {"name": "submit_cv"}}
    else:
        agent.tool_choice = "auto"


@tool(stop_after_tool_call=True)
async def submit_cv(run_context: RunContext, files: Optional[Sequence[File]] = None) -> str:
    """AGENTS.md §2 — yazan taraf. cv_processing_workflow'u çalıştırır, sonucu
    bilgi bankasına yazar. Kriter olsun olmasın her zaman çalışır.

    stop_after_tool_call=True: bu fonksiyonun dönüş değeri LLM'e yeniden
    yorumlatılmadan AYNEN kullanıcıya iletilir ve run orada biter. Bu olmadan,
    agent.tool_choice (pre_hook ile bu fonksiyona zorlanmıştı) her model
    çağrısında yeniden okunduğu için (agno/agent/_run.py) tool sonucunu
    özetleyecek bir sonraki model çağrısı da submit_cv'yi çağırmaya zorlanır ve
    sonsuz döngüye girer — canlı testte tam olarak bu görüldü."""
    if not files:
        return (
            "Değerlendirmemi istiyorsan hangi kriterlere göre bakmamı istediğini "
            "söyle; yeni bir CV eklemek istiyorsan PDF dosyasını gönder."
        )
    dosya = files[0]

    profile, error = await cv_intake.process_cv(dosya)
    if error:
        return error

    candidate_store.write_candidate_markdown(profile, dosya.filename or "cv.pdf")
    return f"'{profile.full_name or dosya.filename}' bilgi bankasına eklendi."


async def evaluate_candidates(
    run_context: RunContext, criteria: list[str], scope_hint: str = ""
) -> str:
    """AGENTS.md §3 — okuyan/değerlendiren taraf. scope_hint boşsa (en yaygın
    senaryo: 'bunları karşılaştır') bilgi bankası tamamen deterministik olarak
    okunur; doluysa (belirli isimler) yine deterministik kelime eşleşmesiyle
    filtrelenir — FilesystemContextProvider.aquery() canlı testte Answer.results'ı
    boş döndürdü (ARCHITECTURE.md §9.3), bu yüzden agentic aramadan vazgeçildi.

    criteria boş gelirse (LLM, instructions'a rağmen kriter sormadan yine de bu
    tool'u çağırırsa) burada da bir güvenlik ağı var — canlı testte router'ın
    kriter yokken submit_cv'yi çağırıp hatalı davrandığı görüldü."""
    if not criteria:
        return "Hangi kriterlere göre değerlendirmemi istersin?"
    if scope_hint:
        docs = candidate_store.find_candidates_by_hint(scope_hint)
    else:
        docs = candidate_store.list_all_candidates()

    if not docs:
        return "Bilgi bankasında eşleşen bir aday bulamadım."

    if len(docs) == 1:
        return await candidate_analysis.analyze_single(docs[0], criteria)

    return await candidate_analysis.analyze_batch(docs, criteria)


router_agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions=(
        "Sen samimi, kısa ve bağlamı koruyan bir Türkçe sohbet asistanısın.\n"
        "Kullanıcı bir PDF belgesi gönderdiyse HER ZAMAN submit_cv'yi çağır. Bu "
        "mesajda YENİ bir dosya eklenmediyse submit_cv'yi ASLA çağırma — 'bu CV', "
        "'bu aday' gibi ifadeler zaten yüklenmiş bir CV'ye atıftır, yeni dosya değil.\n"
        "Kullanıcı somut kriterler belirterek bir ya da birden fazla adayı "
        "değerlendirmek/karşılaştırmak istediğinde evaluate_candidates'ı çağır; "
        "kriterleri ve (varsa) hangi aday(lar)dan bahsettiğini o anki cümleden "
        "çıkarıp argüman olarak geç. Kriterleri ayrıca hatırlamaya çalışma — her "
        "istekte taze gelir.\n"
        "Kullanıcı bir CV'yi değerlendirmek istediğini belirtip HENÜZ somut bir "
        "kriter söylemediyse (örn. 'genel değerlendirme yap', 'bu CV nasıl?') "
        "HİÇBİR TOOL ÇAĞIRMA — önce hangi kriterlere göre değerlendirmen "
        "gerektiğini sor.\n"
        "CV içeriğini asla kendi başına yorumlama/skorlama, bu iş uzman ajanlara ait."
    ),
    tools=[submit_cv, evaluate_candidates],
    pre_hooks=[pre_hook],
    add_history_to_context=True,
    send_media_to_model=False,  # PDF ham baytları LLM'e gitmez, extraction pypdf+ajan üzerinden
    store_media=True,
    markdown=True,
)

# db AgentOS seviyesinde: kendi db'si olmayan her agent/team/workflow'a otomatik
# atanır (agno/os/app.py) — ARCHITECTURE.md §2.
# cwd'ye göre değil bu dosyanın konumuna göre sabit — candidate_store.CANDIDATE_DIR
# ile aynı gerekçe: bot repo kökünden mi src/ içinden mi başlatıldığına göre göreli
# bir yol farklı sonuç verir.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

agent_os = AgentOS(
    agents=[router_agent],
    interfaces=[Telegram(agent=router_agent, token=settings.telegram_token)],
    db=SqliteDb(db_file=str(_DATA_DIR / "agent-os.db")),
)
app = agent_os.get_app()

if __name__ == "__main__":
    # host="0.0.0.0" şart: varsayılan "localhost" sadece bu makineden gelen
    # bağlantıları kabul eder, Tailscale/Headscale üzerinden gelen socat relay'i
    # dışarıdan sayılır ve reddedilir.
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
