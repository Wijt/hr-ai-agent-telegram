"""Uzman ajanlar (AGENTS.md §5-6). Router tarafından seçilmezler:
extraction workflow adımı olarak, analysis submit_cv içinden çağrılır.
db verilmez — AgentOS içinde koşan bileşenler için gerekmiyor, kalıcı olan
Router'ın sohbet geçmişi ve workflow koşuları.
"""

from agno.agent import Agent

from model_factory import get_model
from schemas import CandidateProfile, SingleAnalysisResult

extraction_agent = Agent(
    name="Extraction Agent",
    model=get_model(),
    # Workflow, dosyaları her adıma taşır — PDF baytlarının modele multimodal
    # gitmesini kapatıyoruz; bu ajanın girdisi validate_pdf'in çıkardığı düz metin.
    send_media_to_model=False,
    output_schema=CandidateProfile,
    instructions=(
        "Sana verilen ham CV metninden yalnızca açıkça belirtilmiş bilgileri çıkar. "
        "Emin olmadığın alanları boş bırak, asla uydurma."
    ),
)

analysis_agent = Agent(
    name="Analysis Agent",
    model=get_model(),
    output_schema=SingleAnalysisResult,
    instructions=(
        "Bir İK uzmanı gibi davran. Sana bir aday profili (JSON) ve kullanıcının "
        "değerlendirme kriterleri verilecek. SADECE bu kriterlere göre değerlendir, "
        "kriter dışı özellikleri yorumlama. Güçlü/zayıf yönleri ve somut gelişim "
        "tavsiyelerini Türkçe, okunaklı bir Markdown raporu olarak üret."
    ),
)
