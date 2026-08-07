"""Temel eval suite'i: gerçek agent + gerçek model ile uçtan uca tek case.

Çalıştırma (proje kökünden):
    .venv/Scripts/python evals/smoke.py                # tüm case'ler
    .venv/Scripts/python evals/smoke.py --list         # koşmadan listele
    .venv/Scripts/python evals/smoke.py -v             # run panelleriyle

Sonuçlar db= üzerinden agent-os.db'ye yazılır; AgentOS ayaktayken /eval-runs
endpoint'inden ve os.agno.com/evaluation üzerinden görüntülenir.

Case, kendi test adayını setup'ta knowledgebase'e ekler ve teardown'da siler —
gerçek aday verisine dokunmaz, arkada iz bırakmaz.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Windows konsolu varsayılan cp1252 ile açılıyor ve rich'in özet tablosu Türkçe
# karakterlerde (ş, ı) UnicodeEncodeError ile çöküyordu — çıktıyı UTF-8'e zorla.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from agno.db.sqlite import SqliteDb
from agno.eval import Case, cli

from config import DATA_DIR
from main import agent
from schemas import Education, LanguageSkill, NormalizedCV, PersonalInfo, WorkExperience
from utils.candidate_store import KNOWLEDGE_DIR, normalized_json_path
from utils.model_factory import get_model

_TEST_ID = "eval_test_aday"

# Pydantic modeliyle üretiliyor ki şema değişirse eval de aynı anda kırılsın —
# elle yazılmış, sessizce eskiyen bir JSON string'i olmasın.
_TEST_CV = NormalizedCV(
    personal_info=PersonalInfo(
        full_name="Eval Test Aday",
        title="Backend Developer",
        email="eval.test@example.com",
        phone=None,
        location="İstanbul, Türkiye",
        links=[],
    ),
    summary="Python ağırlıklı 4 yıllık backend deneyimi.",
    work_experience=[
        WorkExperience(
            company="Örnek Yazılım A.Ş.",
            position="Backend Developer",
            start_date="2021-06",
            end_date="Present",
            description="REST API geliştirme, PostgreSQL, mesaj kuyrukları.",
            technologies=["Python", "FastAPI", "PostgreSQL"],
        )
    ],
    education=[
        Education(
            institution="Örnek Üniversitesi",
            degree="Lisans",
            field_of_study="Bilgisayar Mühendisliği",
            end_date="2021-06",
        )
    ],
    skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
    languages=[LanguageSkill(language="Türkçe", proficiency="Native")],
)


def _seed_test_candidate():
    path = normalized_json_path(_TEST_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TEST_CV.model_dump_json(indent=2), encoding="utf-8")


def _remove_test_candidate(context, result):
    shutil.rmtree(KNOWLEDGE_DIR / _TEST_ID, ignore_errors=True)


CASES = (
    # main.py'deki _ADAY_COZUMLEME + _TOOL_SECIMI talimatlarının uçtan uca kontrolü:
    # isimden candidate_id çözülüyor mu, doğru tool çağrılıyor mu, sonuç ham JSON değil
    # okunaklı markdown olarak mı sunuluyor?
    Case(
        name="swot_istegi_dogru_tool_ve_sunum",
        agent=agent,
        input="Eval Test Aday adlı adayın SWOT analizini yapar mısın?",
        tags=("smoke",),
        expected_tool_calls=("analyze_cv_swot",),  # list_files gibi ek çağrılara izin var
        criteria=(
            "Cevap dört SWOT kategorisini de (güçlü yönler, zayıf yönler, fırsatlar, "
            "tehditler) madde madde içermeli, Türkçe olmalı ve ham JSON dökümü "
            "içermemeli. Adayın CV'sindeki gerçek bilgilere (Python/backend profili) "
            "dayanmalı."
        ),
        setup=_seed_test_candidate,
        teardown=_remove_test_candidate,
    ),
)

if __name__ == "__main__":
    sys.exit(
        cli(
            CASES,
            # Judge varsayılanı OpenAI'ın gpt-5-mini'si — Ollama'da çalışırken de eval
            # koşabilsin diye judge botun kendi model seçimini kullanıyor.
            judge_model=get_model(),
            # Botun kendi veritabanı: AgentOS /eval-runs ve os.agno.com buradan okur.
            db=SqliteDb(db_file=str(DATA_DIR / "agent-os.db")),
        )
    )
