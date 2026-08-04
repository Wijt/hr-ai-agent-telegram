from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.knowledge.filesystem import FileSystemKnowledge
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from config import DATA_DIR, settings
from cv_intake import KNOWLEDGE_DIR, intake_pre_hook
from models.model_factory import get_model

KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

fs_knowledge = FileSystemKnowledge(
    base_dir=str(KNOWLEDGE_DIR),
    include_patterns=["*.json", "*.md"],
    exclude_patterns=["_raw", ".git", "__pycache__", "node_modules", ".venv", "venv"],
)

agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions=(
        "Sen samimi, kısa ve bağlamı koruyan bir Türkçe sohbet asistanısın. "
        "Kullanıcı bir CV dosyası yüklediğinde bu otomatik olarak arka planda işlenir; "
        "bunu sen tetiklemezsin. En son yüklenen dosya: {cv_current_file}. "
        "grep_file/list_files/get_file araçları zaten adaylar klasörüne odaklı — "
        "pattern'e 'data/knowledgebase/adaylar' gibi bir yol öneki EKLEME, sadece "
        "'*aday_adı*' gibi göreli bir desen kullan (ör. list_files('*furkan_kaya*')). "
        "Dosya adları '<aday_id>_normalized.json' şeklinde, aday adının snake_case hali. "
        "CV işleme durumu ve sonuçları için TEK GÜVENİLİR KAYNAK bu dosya sistemidir — "
        "kendi hafızana veya varsayımına güvenme, zamanlama yüzünden güncel olmayabilir. "
        "Kullanıcı bir CV'nin durumunu veya detaylarını sorduğunda mutlaka önce "
        "list_files veya grep_file ile ilgili adaya ait bir *_normalized.json oluşmuş mu "
        "kontrol et. Sadece 'işlendi mi, durumu ne' gibi bir soru varsa bu adım yeterli — "
        "dosya bulunması işlemin bittiği anlamına gelir, get_file'ı ÇAĞIRMANA gerek yok. "
        "Kullanıcı içerik/detay istiyorsa (beceriler, deneyim, özet vb.) o zaman get_file "
        "ile oku ve gerçek veriye dayanarak cevap ver. Dosya henüz oluşmamışsa hâlâ "
        "işlendiğini söyle. Kullanıcı 'işlendi ama sen görmüyorsun' derse ona güven, "
        "dosya sistemini tekrar kontrol et, eski varsayımında ısrar etme."
    ),
    pre_hooks=[intake_pre_hook],
    knowledge=fs_knowledge,
    search_knowledge=False,
    tools=[*fs_knowledge.get_tools()],
    session_state={"cv_current_file": None},
    send_media_to_model=False,
    store_media=True,
    markdown=True,
    add_history_to_context=True,
)

agent_os = AgentOS(
    agents=[agent],
    interfaces=[Telegram(agent=agent, token=settings.telegram_token)],
    db=SqliteDb(db_file=str(DATA_DIR / "agent-os.db")),
    tracing=True,
)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
