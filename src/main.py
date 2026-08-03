from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from config import settings
from models.model_factory import get_model

# Aşama 1 (ARCHITECTURE.md §13): tool'suz sohbet ajanı + kalıcı session/geçmiş.
agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions="Sen samimi, kısa ve bağlamı koruyan bir Türkçe sohbet asistanısın.",
    markdown=True,
    add_history_to_context=True,
)

# db AgentOS seviyesinde: kendi db'si olmayan her agent/team/workflow'a otomatik
# atanır (agno/os/app.py) — Aşama 2-3'te eklenecek diğer bileşenler de aynı dosyayı
# tek tanımdan paylaşacak (ARCHITECTURE.md §2).
agent_os = AgentOS(
    agents=[agent],
    interfaces=[Telegram(agent=agent, token=settings.telegram_token)],
    db=SqliteDb(db_file="data/agent-os.db"),
)
app = agent_os.get_app()

if __name__ == "__main__":
    # host="0.0.0.0" şart: varsayılan "localhost" sadece bu makineden gelen
    # bağlantıları kabul eder, Tailscale/Headscale üzerinden gelen socat relay'i
    # dışarıdan sayılır ve reddedilir.
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
