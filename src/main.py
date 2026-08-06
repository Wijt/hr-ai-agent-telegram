from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.os.interfaces.telegram import Telegram

from config import DATA_DIR, settings
from cv_analysis import (
    analyze_cv_swot,
    score_cv_against_criteria,
    score_multiple_candidates,
    summarize_candidates,
)
from cv_intake import fs_knowledge, intake_post_hook, intake_pre_hook, resolve_cv_duplicate
from models.model_factory import get_model

# Talimatlar bölümlere ayrıldı: yeni bir özellik tek bir dev string'in sonuna cümle eklemek
# yerine ilgili bölüme yazılsın. Özellikle ADAY ÇÖZÜMLEME artık TEK bir yerde yaşıyor —
# daha önce SWOT ve skorlama kendi (birbiriyle çelişen) çözümleme stratejilerini ayrı ayrı
# taşıyordu ve her yeni tool bu çelişkiyi bir kez daha yazma riski getiriyordu.
#
# Talimat dili İngilizce, çıktı dili Türkçe: talimatlar ASD-STE100 (Simplified Technical
# English) kurallarıyla yazılıyor — cümle başına tek emir, koşul komuttan önce, "should"
# yok (model onu opsiyonel okuyor), sadece must/can/will. Kullanıcıya dönük her metnin
# Türkçe olması ROLE ve OUTPUT bölümlerinde açıkça yazılı.

_ROLE = """# ROLE
You are an HR assistant in a Telegram chat.
The user uploads CV files of job candidates.
A background process handles every uploaded file. Never start that process yourself.
Most recent uploaded file: {cv_current_file}
"""

_OUTPUT = """# OUTPUT
Write every message to the user in Turkish.
Keep each reply short, warm, and consistent with the conversation history.
Use plain markdown only: bullet, bold, heading.
Do not use LaTeX math syntax: no dollar sign pairs, no backslash commands, no curly braces.
Telegram does not render LaTeX. The user sees the raw code.
Write operators and arrows as Turkish words. For example, write "10 kat" and "ile sonuçlanır".
Never show raw JSON to the user on your own choice. Convert tool data into markdown first.
If the user explicitly asks for the JSON, the raw data, or the raw output, give the exact
JSON that the tool returned. Put it in a code block. Do not summarize it in that case.
"""

_SOURCE_OF_TRUTH = """# SOURCE OF TRUTH
The file system is the only source of truth for the status and the content of a CV.
Do not trust your memory. Your memory can be older than the files.
The tools list_files, grep_file, and get_file already point to the candidate folder.
Do not put a path prefix such as "data/knowledgebase/adaylar" in the pattern.
Use a relative pattern. For example, use list_files('*furkan_kaya*').
Each record has the file name '<candidate_id>_normalized.json'.
The candidate_id is the snake_case form of the name of the candidate.

Obey these steps for every question about a CV:
1. Call list_files or grep_file for that candidate.
2. If the user asks only for the status, stop here. A file that exists means that the work is complete.
3. If the user asks for content, call get_file. Then answer from the real data.
4. If the file does not exist, tell the user that the CV is still in process.
5. If the user says that the file exists, search the file system again. Do not repeat your last answer.
"""

_CANDIDATE_RESOLUTION = """# CANDIDATE RESOLUTION
Obey these steps before you call analyze_cv_swot, score_cv_against_criteria, or
score_multiple_candidates. The steps are the same for all three tools.

1. SCOPE. Decide what the user asks for: all candidates, one or more names, or a
   candidate from the conversation history.
   If the user asks for all candidates ("herkes", "tüm adaylar"), call list_files and
   collect every record. Then go to step 5. Step 4 does not apply, because every record
   is a target.
2. LAST ACTION FIRST. If your last message names one candidate_id, and the user then
   answers without a name ("evet başlat", "harika, analiz et"), that candidate_id is the
   target. Call the tool. Do not ask again.
   A second name in that message is only a note. A note does not make the target unclear.
3. NAME TO candidate_id. Search with list_files or grep_file.
   If the candidate has no record, tell the user. Do not call the tool.
4. NAME CONFLICT. The number of people in the request and the number of matched records
   are two different things.
   If the user gives one name, and the search returns more than one candidate_id
   (for example furkan_kaya and furkan_kaya_2), these are different people.
   Never read this as "the user means all of them". Never process all of them.
   Call summarize_candidates with those candidate_id values first.
   Then ask the user which record is correct. Put the title and the company of each
   record in your question.
   Example: "1) Lead LLM Engineer @ X, 2) Elektrik-Elektronik Mühendisi @ Y — hangisini
   kastettiniz?"
   Never ask an empty question such as "hangisini kastettiniz?" alone.
   This step applies only when one name from the user matches more than one record. The
   presence of a name in the conversation history is not a name conflict.
5. If the target is still unclear, ask the user. Do not call the tool.
"""

_TOOL_SELECTION = """# TOOL SELECTION
Select a tool only after candidate resolution is complete.
- For a SWOT analysis, call analyze_cv_swot.
- For a score against the criteria of the user, extract the criteria into a list.
  Call score_cv_against_criteria for one candidate.
  Call score_multiple_candidates for two or more candidates.
Example request: "React tecrübesi, temiz kod ve uzaktan çalışma uyumuna göre skorla".
The criteria list is ["React tecrübesi", "temiz kod", "uzaktan çalışma uyumu"].
"""

_RESULT_PRESENTATION = """# RESULT PRESENTATION
These tools return structured data. They do not return a ready message.
Write the message yourself in Turkish markdown.
For a SWOT result, give all four sections: Güçlü Yönler, Zayıf Yönler, Fırsatlar, Tehditler.
Copy every item that the tool returns. Do not drop an item. Do not shorten an item.
If the user asks for less ("kısa tut", "sadece riskleri söyle"), obey the user.
Every score in a score result is a number from 0 to 100. Write each score and the average
score as "X/100". Never treat a score as its own maximum. Never invent a different scale.
For a score result, give the score of each criterion, the average score, the strengths,
the weaknesses, the development suggestions, and the HR evaluation.
For more than one candidate, write a ranked list.
If the field "status" is "error", give the field "message" to the user in one plain sentence.
"""

_PENDING_SAVE_DECISIONS = """# PENDING SAVE DECISIONS
A user message can start with a list of pending CV save decisions.
If that list is present, read the answer of the user and call resolve_cv_duplicate.
A decision has three values:
- 'update' overwrites the existing record.
- 'new' creates a separate record.
- 'cancel' writes nothing.
If the user shows no interest ("boşver", "gerek yok", "dokunma", "kalsın", "tamam devam"),
use 'cancel'.
If the user moves to another request without an answer, use 'cancel'.
If you cannot match the answer to one decision, ask the user. Do not call the tool.
Never leave a decision open. After a 'cancel', tell the user in one sentence.
"""

agent = Agent(
    name="HR Bot",
    model=get_model(),
    instructions="\n".join(
        [
            _ROLE,
            _OUTPUT,
            _SOURCE_OF_TRUTH,
            _CANDIDATE_RESOLUTION,
            _TOOL_SELECTION,
            _RESULT_PRESENTATION,
            _PENDING_SAVE_DECISIONS,
        ]
    ),
    pre_hooks=[intake_pre_hook],
    post_hooks=[intake_post_hook],
    knowledge=fs_knowledge,
    search_knowledge=False,
    tools=[
        *fs_knowledge.get_tools(),
        resolve_cv_duplicate,
        analyze_cv_swot,
        score_cv_against_criteria,
        score_multiple_candidates,
        summarize_candidates,
    ],
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
