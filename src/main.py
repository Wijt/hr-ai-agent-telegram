from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from bot import chat_agent
from config import settings
from workflows import cv_processing_workflow

# db AgentOS seviyesinde: kendi db'si olmayan her agent/workflow'a otomatik atanır
# (agno/os/app.py) — chat_agent'ın sohbet geçmişi ve workflow koşuları aynı dosyada.
agent_os = AgentOS(
    agents=[chat_agent],
    workflows=[cv_processing_workflow],
    interfaces=[Telegram(agent=chat_agent, token=settings.telegram_token)],
    db=SqliteDb(db_file="data/agent-os.db"),
)
app = agent_os.get_app()

if __name__ == "__main__":
    # host="0.0.0.0" şart: varsayılan "localhost", Tailscale/Headscale üzerinden
    # gelen socat relay bağlantılarını dışarıdan sayıp reddeder.
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
