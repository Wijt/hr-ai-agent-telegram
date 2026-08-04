from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from config import settings
from models.model_factory import get_model

agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions="Sen samimi, kısa ve bağlamı koruyan bir Türkçe sohbet asistanısın.",
    markdown=True,
    add_history_to_context=True,
)

agent_os = AgentOS(
    agents=[agent],
    interfaces=[Telegram(agent=agent, token=settings.telegram_token)],
    db=SqliteDb(db_file="data/agent-os.db"),
)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="main:app", host="0.0.0.0", port=7777, reload=True)
