from agno.agent import Agent
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from config import settings
from models.model_factory import get_model

# Aşama 0 (ARCHITECTURE.md §13): tool'suz, en yalın sohbet ajanı.
# Amaç sadece Telegram <-> AgentOS bağlantısının uçtan uca çalıştığını doğrulamak.
agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions="Sen samimi, kısa ve bağlamı koruyan bir Türkçe sohbet asistanısın.",
    markdown=True,
)

agent_os = AgentOS(
    agents=[agent],
    interfaces=[Telegram(agent=agent, token=settings.telegram_token)],
)
app = agent_os.get_app()

if __name__ == "__main__":
    # host="0.0.0.0" şart: varsayılan "localhost" sadece bu makineden gelen
    # bağlantıları kabul eder, Tailscale/Headscale üzerinden gelen socat relay'i
    # dışarıdan sayılır ve reddedilir.
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
