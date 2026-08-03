"""Bir CV'yi işlemenin tek, paylaşılan tarifi (ARCHITECTURE.md §6):
validate_pdf (function, LLM'siz kapı) → extract_cv (Agent, output_schema).

Tekli mod (bot.submit_cv) bunu bir kez çalıştırır; Aşama 3'te toplu mod
aynı nesneyi N kez paralel çalıştıracak.
"""

from agno.run.workflow import WorkflowRunOutput
from agno.workflow import Step, StepInput, StepOutput, Workflow

from agents import extraction_agent
from pdf_validator import validate_pdf


def validate_pdf_step(step_input: StepInput) -> StepOutput:
    files = step_input.files or []
    if not files:
        # Telegram 20MB üzeri dosyayı hiç indirmez — workflow'a dosya ulaşmaz.
        return StepOutput(content="Dosyayı alamadım. 20MB'tan küçük bir PDF dener misin?", stop=True)
    raw = files[0].content if isinstance(files[0].content, bytes) else b""
    text, error = validate_pdf(raw)
    if error:
        # Agno'nun resmi early-stop deseni: extract_cv hiç çalışmaz, LLM çağrısı yapılmaz.
        return StepOutput(content=error, stop=True)
    return StepOutput(content=text)


cv_processing_workflow = Workflow(
    name="CV Processing",
    steps=[
        Step(name="validate_pdf", executor=validate_pdf_step),
        Step(name="extract_cv", agent=extraction_agent),
    ],
)


def stopped_early(run_output: WorkflowRunOutput) -> bool:
    """Doğrulama kapısında mı durdu? Agno'da bunun ayrı bir alanı yok:
    status 'completed' kalır, son adımın stop bayrağına bakılır."""
    return bool(run_output.step_results) and bool(run_output.step_results[-1].stop)
