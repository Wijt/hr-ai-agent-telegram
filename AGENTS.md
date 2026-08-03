# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md`'de tanımlanan sistemin ajan/tool/pipeline envanteri. Bu dosya, her
parçanın *neden var olduğunu*, *ne zaman çağrıldığını* ve *hangi şemayla konuştuğunu*
kayıt altına alır — implementasyon sırasında `src/hrbot/agents/` altındaki kodun
doğrudan karşılığıdır.

## 0. Çalışma İlkeleri (KISS)

Bu proje üzerinde çalışan herkes (bu oturum dahil, gelecekteki oturumlar dahil)
aşağıdaki ilkelere uyar. Bu bölüm var olduğu için bu ilkeler her seferinde yeniden
anlatılmaz — kod yazmadan önce buraya bakılır.

1. **Keep It Simple, Stupid — ama basitlik tutarlılık demektir, framework'ten kaçınmak
   değil.** Bir CV'yi işlemenin (doğrula → çıkar → [ileride: bilgi bankasına kaydet])
   tek, paylaşılan bir tarifi var: `cv_processing_workflow`. Tekli mod bunu bir kez
   çalıştırır, toplu mod **aynı tarifi** N aday için paralel çalıştırır. İki farklı
   mimari (biri düz fonksiyon zinciri, biri Workflow) tutmak — ilk bakışta "daha az
   framework kullanımı" gibi görünse de — aslında iki ayrı deseni öğrenip bakım
   yapmayı gerektirdiği için daha karmaşıktır. Ayrıca Agno'nun kendi resmi örnekleri,
   paralellik olmasa bile ardışık çok-adımlı ajan zincirlerini hep `Workflow` ile
   kuruyor — bu bizim icat ettiğimiz bir şey değil, framework'ün kendi idiom'u
   (bkz. madde 4). Basitlik = **tek, tutarlı, test edilmiş bir tarif; onu tekrar
   tekrar kullanmak.**
2. **Kompleksite adım adım, gerektikçe eklenir.** Baştan "olası her ihtiyacı"
   karşılayan bir mimari kurulmaz. En basit çalışan hâliyle başlanır, bir sonraki
   katman ancak bir öncekinin çalıştığı doğrulandıktan sonra eklenir. Aşamalı plan
   için bkz. `ARCHITECTURE.md` §13.
3. **Hello World önce.** İlk yazılacak kod, ucu ucuna çalışan en minimal iskelet
   olmalı (Telegram bağlantısı + tek bir tool'suz sohbet ajanı) — CV analizi, batch
   skorlama, kriter yönetimi gibi hiçbir özellik olmadan. Bu çalıştıktan sonra
   üstüne katman katman eklenir.
4. **Sektör best practice'i araştırılır, uygulanır.** Bir şey yazmadan önce Agno'nun
   resmi dokümantasyonu/örnek kodları (ya da ilgili framework'ün resmi kaynağı)
   aranır, oradaki idiom'lar takip edilir. Örneklerden **sapılmaz.**
5. **Sapma gerekiyorsa, önce sorulur.** Best practice'ten farklı bir yol izlemek
   gerçekten gerekiyorsa (performans, ödev gereksinimi, vb. somut bir gerekçeyle),
   bu **kullanıcıya gerekçesiyle sorulup onay alınmadan** yapılmaz.

## Tasarım İlkesi

Tek bir "her şeyi yapan" ajan yerine, **bir router + üç uzman ajan + tek paylaşılan
CV pipeline'ı** modeli:

- **Router Agent** — Telegram'a bağlı tek ajan. Kullanıcıyla doğrudan konuşan bu.
  Kendi başına CV analiz etmez; ne zaman hangi tool'un devreye gireceğine
  tool-calling ile karar verir.
- **`cv_processing_workflow`** — bir adayı (doğrula → çıkar) işlemenin **tek, paylaşılan
  tarifi**. Hem tekli modda (bir kez) hem toplu modda (N kez, paralel) **birebir aynı
  nesne** çalıştırılır. Kod tekrarı yok, iki ayrı mimari yok.
- **Extraction / Analysis / Scoring** ajanları LLM tarafından *seçilmez* —
  `cv_processing_workflow`'un bir adımı olarak (Extraction) ya da onu saran bir
  fonksiyon/executor içinden (Analysis, Scoring) çağrılır. Bu ayrım kararlılık için
  kritik (bkz. `ARCHITECTURE.md` §5).

---

## 1. Router Agent

**Dosya:** `agents/chat_agent.py`
**Bağlı olduğu arayüz:** Agno `Telegram` interface (`AgentOS(interfaces=[Telegram(agent=router_agent)])`)
**Model:** `model_factory.get_model()` (varsayılan OpenAI, env ile Ollama'ya geçer)
**db:** `SqliteDb` — session/history + `session_state` kalıcılığı
**Diğer ayarlar:** `send_media_to_model=False`, `store_media=True` — PDF ham içeriği
LLM'e gönderilmez, sadece tool erişimi için saklanır (bkz. `ARCHITECTURE.md` §10.1).
**`pre_hook`:** o turda ekli dosya (`files`) varsa `tool_choice="submit_cv"` olarak
sabitlenir — dosya geldiğinde `submit_cv`'nin çağrılması LLM kararına değil koda
bağlıdır (bkz. `ARCHITECTURE.md` §5).

**Instructions (özet, Türkçe):**
- Varsayılan davranış: samimi, kısa, bağlamı koruyan bir sohbet asistanı gibi yanıt ver.
- Kullanıcı puanlama/kriter tanımlıyorsa (`"...göre skorla"`, `"...kriterlerine göre
  değerlendir"` gibi ifadeler) → `set_dynamic_criteria` tool'unu çağır.
- Kullanıcı `/batch_analyze` yazdıysa veya birden fazla CV göndereceğini belirtiyorsa
  → `start_batch_session` çağır.
- Kullanıcı bir PDF belgesi gönderdiyse → **her zaman** `submit_cv` çağır (karar
  verme, tool zaten mevcut duruma göre doğru şeyi yapacak).
- Kullanıcı `/done` yazdıysa → `finalize_batch` çağır.
- Asla CV içeriğini kendi başına yorumlama/skorlama — bu iş uzman ajanlara ait.

**Tool envanteri:**

| Tool | İmza | Ne yapar |
|---|---|---|
| `set_dynamic_criteria` | `(run_context, criteria: list[str]) -> str` | Kullanıcının serbest metnini LLM zaten tool-call argümanı olarak listeye çevirir; `session_state["dynamic_criteria"]` güncellenir. |
| `start_batch_session` | `(run_context) -> str` | `session_state["mode"] = "collecting_batch"`, `batch_files = []`. Kriter tanımlı değilse kullanıcıyı önce kritere yönlendirir. |
| `submit_cv` | `(run_context, files: Optional[Sequence[File]] = None) -> str` | Bkz. §2. **idle**'da `cv_processing_workflow`'u hemen çalıştırıp analiz eder; **batch**'te dosyayı işlemeden biriktirir (işleme `finalize_batch`'e ertelenir — bkz. §3). `pre_hook` sayesinde dosya varken çağrılması garanti. |
| `finalize_batch` | `(run_context) -> str` | Bkz. §3. Biriktirilen her dosya için **aynı `cv_processing_workflow`'u paralel olarak** çalıştırır, skorlar, JSON döner, mode'u `idle`'a çeker. |

**Kullanılmayan/gerek olmayan tool'lar:** `reset` — Agno'nun native `/new` komutu
session_state'i zaten sıfırlıyor, tekrar yazılmayacak.

---

## 2. `cv_processing_workflow` — Tek, Paylaşılan Tarif

Bir adayı işlemenin **tek** tanımı. Hem tekli hem toplu mod bunu birebir aynı nesne
olarak kullanır — biri bir kez, öbürü N kez paralel:

```python
cv_processing_workflow = Workflow(
    steps=[
        Step(name="validate_pdf", executor=validate_pdf_step),   # PdfValidator sarmalar, bkz. ARCHITECTURE.md §9
        Step(name="extract_cv", agent=extraction_agent),          # -> CandidateProfile (output_schema)
        # Aşama 4'te (opsiyonel, bkz. ARCHITECTURE.md §13) eklenecek:
        # Step(name="store_to_knowledge", executor=store_to_knowledge_step),
    ]
)

def validate_pdf_step(step_input: StepInput) -> StepOutput:
    sonuc = PdfValidator.validate(step_input.files[0].content, step_input.files[0].filename)
    if sonuc.status != VALID:
        return StepOutput(content=sonuc.user_message, stop=True)   # pipeline burada durur
    return StepOutput(content=sonuc.extracted_text)
```

`extract_cv` çıktısı (`CandidateProfile`, tipli) → çağıranın (`single_cv_workflow`
ya da batch'teki executor) `previous_step_content`'i olur.

---

## 3. Tekli Mod — `single_cv_workflow`

`cv_processing_workflow`'u bir adım olarak sarar (nested workflow-as-step), sonuna
sadece tekli modda gereken nitel analiz adımını ekler:

```python
single_cv_workflow = Workflow(steps=[
    Step(name="process", workflow=cv_processing_workflow),
    Step(name="analyze_cv", executor=analyze_cv_step),
])

def analyze_cv_step(step_input: StepInput) -> StepOutput:
    profile = step_input.previous_step_content                       # CandidateProfile
    criteria = json.loads(step_input.get_input_as_string())["criteria"]
    rapor = analysis_agent.run(
        f"Aday profili: {profile.model_dump_json()}\nKriterler: {criteria}"
    )
    return StepOutput(content=rapor.content)                          # SingleAnalysisResult


def submit_cv(run_context, files):
    if not files:
        return "Bir PDF dosyası göndermelisin."
    criteria = session_state["dynamic_criteria"]

    if session_state["mode"] == "collecting_batch":
        session_state["batch_files"].append(files[0])                 # HAM dosya, işlenmeden biriktirilir
        if len(session_state["batch_files"]) == 5:
            return finalize_batch(run_context)
        return f"{len(session_state['batch_files'])}/5 CV alındı. Daha fazla gönder ya da /done yaz."

    else:  # idle -> tekli analiz, HEMEN çalıştırılır
        if not criteria:
            return "Bu CV'yi hangi kriterlere göre değerlendirmemi istersin?"
        sonuc = single_cv_workflow.run(input=json.dumps({"criteria": criteria}), files=files)
        if sonuc.stopped:
            return sonuc.content                                       # validate_pdf hatası
        return sonuc.content.markdown_report
```

---

## 4. Toplu Mod — `finalize_batch`: Aynı Tarifi N Kez, Paralel

Toplu mod, `submit_cv` sırasında **hiçbir şey işlemez** — sadece ham dosyaları
biriktirir (bkz. §3). Tüm işleme (doğrulama + çıkarım + skorlama), `finalize_batch`
çağrıldığında **hepsi aynı anda**, her biri **aynı `cv_processing_workflow`'u**
çalıştıran bir `Parallel` bloğunda yapılır:

```python
class ProcessAndScoreExecutor:
    """Her paralel dal bu executor'ın bir örneği — kendi dosyasını closure'da taşır,
    ama hepsi AYNI cv_processing_workflow nesnesini çağırır."""

    def __init__(self, file: File, criteria: list[str]):
        self.file = file
        self.criteria = criteria

    async def __call__(self, step_input: StepInput) -> StepOutput:
        sonuc = await cv_processing_workflow.arun(files=[self.file])   # <-- tekli modla BİREBİR aynı çağrı
        if sonuc.stopped:
            return StepOutput(
                content={"filename": self.file.filename, "error": sonuc.content},
                success=False,
            )
        profile = sonuc.content                                        # CandidateProfile
        skor = await scoring_agent.arun(
            f"Aday profili: {profile.model_dump_json()}\nKriterler: {self.criteria}"
        )
        return StepOutput(content={
            "filename": self.file.filename,
            "profile": profile,
            "score": skor.content,
        })


def finalize_batch(run_context):
    if session_state["mode"] != "collecting_batch":
        return "Şu an toplanan bir CV grubu yok."
    if not session_state["batch_files"]:
        return "Henüz hiç CV göndermedin."

    criteria = session_state["dynamic_criteria"]
    branches = [
        Step(name=f"candidate_{i}", executor=ProcessAndScoreExecutor(file, criteria))
        for i, file in enumerate(session_state["batch_files"])
    ]
    batch_workflow = Workflow(steps=[
        Parallel(*branches, name="process_all"),
        Step(name="rank_top3", executor=rank_top3_fn),   # averageScore hesabı + sıralama, LLM'siz
    ])
    sonuc = batch_workflow.run()

    session_state["mode"] = "idle"
    session_state["batch_files"] = []
    return sonuc.content   # BatchAnalysisResult (JSON, ödev şemasına birebir)
```

**Bu tasarımın kilit noktası:** `ProcessAndScoreExecutor.__call__` içindeki
`cv_processing_workflow.arun(files=[self.file])` satırı, `single_cv_workflow`'un
`process` adımının yaptığı **birebir aynı çağrı**. Tekli/toplu arasındaki tek fark,
kaç kez ve ne zaman (hemen mi, `finalize_batch`'te toplu mu) çağrıldığı — pipeline'ın
kendisi değil.

**Bilinen trade-off:** Doğrulama artık `finalize_batch`'e kadar ertelendiği için,
5 CV'den biri bozuksa kullanıcı bunu ancak hepsini gönderip `/done` dedikten sonra
öğrenir (erken geri bildirim yok). Bunun karşılığında tek, tutarlı bir pipeline elde
ediyoruz — bilinçli bir tercih, `ARCHITECTURE.md` §11'de kayıtlı.

---

## 5. Extraction Agent

**Dosya:** `agents/extraction_agent.py`
**Rolü:** LLM Extraction — ham, dağınık CV metnini ortak `CandidateProfile` JSON
şemasına normalize eder (ödevin "farklı formatları standartlaştırma" gereksinimi).
**`output_schema`:** `CandidateProfile` (`full_name`, `skills`, `work_experience`,
`languages`, `education`)
**Instructions (özet):** *"Sana verilen ham CV metninden yalnızca açıkça belirtilmiş
bilgileri çıkar. Emin olmadığın alanları boş bırak, uydurma."*
**Çağrılma şekli:** `cv_processing_workflow`'un 2. adımı — düz bir Agent step.
Hem tekli hem toplu modda **aynı şekilde** çağrılır çünkü ikisi de aynı workflow'u
kullanır.

## 6. Analysis Agent (tekli CV)

**Dosya:** `agents/analysis_agent.py`
**Rolü:** Tek bir `CandidateProfile` + kullanıcının dinamik kriterlerini alıp nitel
bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult` (`candidate_name`, `strengths`,
`weaknesses`, `recommendations`, `markdown_report`)
**Instructions (özet):** *"Bir İK uzmanı gibi davran. Sadece verilen kriterlere göre
değerlendir, kriter dışı özellikleri yorumlama. Güçlü/zayıf yönleri ve somut gelişim
tavsiyelerini Türkçe, okunaklı bir Markdown raporu olarak üret."*
**Çağrılma şekli:** `single_cv_workflow`'un `analyze_cv` adımı içinden. Sadece tekli
modda kullanılır — toplu mod nitel rapor değil, skor üretir (bkz. Scoring Agent).

## 7. Scoring Agent (çoklu CV)

**Dosya:** `agents/scoring_agent.py`
**Rolü:** Bir `CandidateProfile` + dinamik kriter listesini alıp **her kritere ayrı
ayrı 0-100 arası puan** verir (ödevin `dynamicScores` alanı).
**`output_schema`:** `CandidateScore` alt kümesi — `dynamicScores: dict[str, int]`,
`hrEvaluation: str` (kısa gerekçe).
**Çağrılma şekli:** `ProcessAndScoreExecutor` içinden, `cv_processing_workflow`
tamamlandıktan **hemen sonra**, aynı paralel dal içinde. Tüm dallar Agno'nun native
`Parallel`'ı ile aynı anda çalışır — elle `asyncio.gather`/`Semaphore` yazılmıyor.
**Sıralama:** `averageScore` `rank_top3_fn` içinde Python'da hesaplanır (LLM'e
bırakılmaz — aritmetik ortalama deterministik olmalı), ilk 3 aday `rank` ile döner.

---

## 8. Model Sağlayıcı Soyutlaması

**Dosya:** `models/model_factory.py`

```python
def get_model():
    provider = settings.MODEL_PROVIDER  # "openai" (varsayılan) | "ollama"
    if provider == "ollama":
        from agno.models.ollama import Ollama
        return Ollama(id=settings.OLLAMA_MODEL_ID, host=settings.OLLAMA_BASE_URL)
    from agno.models.openai import OpenAIChat
    return OpenAIChat(id=settings.OPENAI_MODEL_ID)
```

Tüm ajanlar (Router, Extraction, Analysis, Scoring) modeli bu fabrikadan alır —
Ollama'ya geçiş tek bir env değişkeni (`MODEL_PROVIDER=ollama`) ile yapılacak, kod
değişikliği gerekmeyecek. **Not:** Ollama'ya geçildiğinde seçilecek modelin
tool-calling / structured-output destekleyen bir model olması gerekir (örn.
`qwen2.5`, `llama3.1`) — bu ARCHITECTURE.md'ye de not düşülmüştür.

## 9. Session State Şeması (özet — detay `ARCHITECTURE.md` §4)

```python
{
    "mode": "idle" | "collecting_batch",
    "dynamic_criteria": list[str] | None,
    "batch_files": list[File],   # HAM, işlenmemiş dosyalar — extraction finalize_batch'e ertelenir
}
```
