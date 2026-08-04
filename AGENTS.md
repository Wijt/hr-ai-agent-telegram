# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md` sistemin genel tasarımını anlatır. Bu dosya, sistemin ajan, tool,
ve pipeline listesini anlatır. Her parçanın neden var olduğunu kaydeder. Her
parçanın ne zaman çağrıldığını kaydeder. Her parçanın hangi şemayla konuştuğunu
kaydeder. Bu dosya, `src/` altındaki kodun doğrudan karşılığıdır.

## 0. Çalışma İlkeleri (KISS)

Bu ilkeler tüm proje için geçerlidir. Bu ilkeleri şu an uygula. Bu ilkeleri gelecek
oturumlarda da uygula. Bu bölüm bunun için var — bu ilkeleri tekrar açıklama. Kod
yazmadan önce bu bölüme bak.

1. **Basit tut.** Basitlik tutarlılık demektir. Basitlik framework'ten kaçınmak
   demek değildir. Bir CV'yi işlemek için tek bir tarif kullan: `cv_processing_workflow`.
   Bu tarif önce doğrular, sonra çıkarır. (İleride bir adım daha eklenecek: bilgi
   bankasına kaydetme.) Tekli mod bu tarifi bir kez çalıştırır. Toplu mod aynı
   tarifi N aday için paralel çalıştırır. İki ayrı mimari kurma — biri düz fonksiyon
   zinciri, biri Workflow. İki ayrı mimari daha az framework kullanımı gibi görünür.
   Ama iki ayrı mimari iki ayrı deseni öğretir, ve iki ayrı deseni bakımda tutmayı
   gerektirir. Bu daha karmaşıktır. Agno'nun resmi örnekleri de ardışık ajan
   zincirlerini hep `Workflow` ile kurar — paralellik olmasa bile (bkz. madde 4).
   Bu bizim icadımız değildir. Bu, framework'ün kendi kuralıdır. Tek, tutarlı, test
   edilmiş bir tarif kullan. Bu tarifi tekrar tekrar kullan.
2. **Kompleksiteyi adım adım ekle.** Baştan her olası ihtiyacı karşılayan bir
   mimari kurma. En basit çalışan hâlle başla. Bir sonraki katmanı, ancak bir
   öncekinin çalıştığını doğruladıktan sonra ekle. Aşamalı plan `ARCHITECTURE.md`
   §13'tedir.
3. **Önce Hello World yaz.** İlk kod, uçtan uca çalışan en küçük iskelet olmalıdır:
   Telegram bağlantısı ve tek bir sohbet ajanı, hiçbir araç (tool) olmadan. Bu ilk
   sürümde CV analizi yoktur. Toplu skorlama yoktur. Kriter yönetimi yoktur. Bu
   iskelet çalıştıktan sonra, üstüne katman katman ekle.
4. **Sektörün en iyi uygulamalarını araştır ve uygula.** Kod yazmadan önce Agno'nun
   resmi dokümanlarını ve örnek kodlarını ara. Başka bir framework kullanıyorsan,
   onun resmi kaynağını ara. Bulduğun örneklerin desenini izle. Örneklerden sapma.
5. **Sapman gerekiyorsa, önce sor.** En iyi uygulamadan farklı bir yol izlemen
   gerçekten gerekiyorsa (performans veya ödev gereksinimi gibi somut bir sebeple),
   bunu kullanıcıya gerekçesiyle sor. Onay almadan yapma.

## Tasarım İlkesi

Bu proje bir "her şeyi yapan tek ajan" modeli kullanmaz. Bunun yerine bir router,
üç uzman ajan, ve tek bir paylaşılan CV pipeline'ı kullanır:

- **Router Agent** — Telegram'a bağlı tek ajandır. Kullanıcıyla doğrudan konuşur.
  Kendisi CV analiz etmez. Hangi tool'un ne zaman çalışacağına tool-calling ile
  karar verir.
- **`cv_processing_workflow`** — bir adayı işlemenin tek, paylaşılan tarifidir. Bu
  tarif önce doğrular, sonra çıkarır. Tekli mod bu tarifi bir kez çalıştırır. Toplu
  mod aynı nesneyi N kez, paralel çalıştırır. Bu tasarımda kod tekrarı yoktur. İki
  ayrı mimari yoktur.
- **Extraction, Analysis, ve Scoring ajanları** — LLM bu ajanları seçmez.
  Extraction, `cv_processing_workflow`'un bir adımı olarak çalışır. Analysis ve
  Scoring, bu tarifi saran bir fonksiyon içinden çalışır. Bu ayrım kararlılık için
  kritiktir (bkz. `ARCHITECTURE.md` §5).

---

## 1. Router Agent

**Dosya:** `agents/chat_agent.py`
**Bağlı olduğu arayüz:** Agno `Telegram` interface (`AgentOS(interfaces=[Telegram(agent=router_agent)])`)
**Model:** `model_factory.get_model()` (varsayılan OpenAI, env ile Ollama'ya geçer)
**db:** Router Agent'ın kendi `db`'si yoktur. `db`, `AgentOS(db=SqliteDb(...))`
seviyesinde tanımlanır. Agno bu `db`'yi, kendi `db`'si olmayan her agent, team, ve
workflow'a otomatik atar (bkz. `ARCHITECTURE.md` §2). Aşama 2-3'te eklenecek
bileşenler aynı dosyayı bu tek tanımdan paylaşır. Her bileşene ayrı `db=` yazma.
**Diğer ayarlar:** `send_media_to_model=False`, `store_media=True`. PDF'in ham
içeriği LLM'e gönderilmez. PDF sadece tool erişimi için saklanır (bkz.
`ARCHITECTURE.md` §10.1).
**`pre_hook`:** O turda ekli dosya (`files`) varsa, `pre_hook` `tool_choice`'u
`submit_cv`'ye sabitler. Dosya geldiğinde `submit_cv` çağrılır — bu LLM'in
kararına değil, koda bağlıdır (bkz. `ARCHITECTURE.md` §5).

**Instructions (özet, Türkçe):**
- Varsayılan davranış: samimi, kısa, bağlamı koruyan bir sohbet asistanı gibi yanıt ver.
- Kullanıcı puanlama/kriter tanımlıyorsa (`"...göre skorla"`, `"...kriterlerine göre
  değerlendir"` gibi ifadeler) → `set_dynamic_criteria` tool'unu çağır.
- Kullanıcı `/batch_analyze` yazdıysa veya birden fazla CV göndereceğini belirtiyorsa
  → `start_batch_session` çağır.
- Kullanıcı bir PDF belgesi gönderdiyse → her zaman `submit_cv` çağır. Karar
  verme — tool zaten doğru şeyi yapar.
- Kullanıcı `/done` yazdıysa → `finalize_batch` çağır.
- CV içeriğini kendi başına yorumlama. CV içeriğini kendi başına skorlama. Bu iş
  uzman ajanlara aittir.

**Tool envanteri:**

| Tool | İmza | Ne yapar |
|---|---|---|
| `set_dynamic_criteria` | `(run_context, criteria: list[str]) -> str` | Kullanıcının serbest metnini LLM zaten tool-call argümanı olarak listeye çevirir. `session_state["dynamic_criteria"]`'i günceller. |
| `start_batch_session` | `(run_context) -> str` | `session_state["mode"] = "collecting_batch"`, `batch_files = []`. Kriter tanımlı değilse, kullanıcıyı önce kritere yönlendirir. |
| `submit_cv` | `(run_context, files: Optional[Sequence[File]] = None) -> str` | Bkz. §2. **idle**'da `cv_processing_workflow`'u hemen çalıştırır ve analiz eder. **batch**'te dosyayı işlemeden biriktirir (işleme `finalize_batch`'e ertelenir — bkz. §3). `pre_hook` dosya varken çağrılmasını garanti eder. |
| `finalize_batch` | `(run_context) -> str` | Bkz. §3. Biriktirilen her dosya için aynı `cv_processing_workflow`'u paralel çalıştırır, skorlar, JSON döner, mode'u `idle`'a çeker. |

**Kullanılmayan tool:** `reset`. Agno'nun native `/new` komutu session_state'i
zaten sıfırlar. Ayrı bir `reset` tool'u yazma.

---

## 2. `cv_processing_workflow` — Tek, Paylaşılan Tarif

Bir adayı işlemenin tek tanımı budur. Tekli mod ve toplu mod bunu aynı nesne
olarak kullanır. Tekli mod bir kez çalıştırır. Toplu mod N kez, paralel çalıştırır.

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

`extract_cv` çıktısı tipli bir `CandidateProfile`'dır. Bu çıktı, çağıranın
(`single_cv_workflow` ya da toplu moddaki executor) `previous_step_content`'i olur.

---

## 3. Tekli Mod — `single_cv_workflow`

`single_cv_workflow`, `cv_processing_workflow`'u bir adım olarak sarar (nested
workflow-as-step). Sonuna sadece tekli modda gereken nitel analiz adımını ekler:

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

## 4. Toplu Mod — `finalize_batch`: Aynı Tarif, N Kez, Paralel

Toplu modda, `submit_cv` hiçbir dosyayı işlemez. `submit_cv` sadece ham dosyaları
biriktirir (bkz. §3). `finalize_batch` çağrıldığında, tüm işleme (doğrulama +
çıkarım + skorlama) başlar. Bu işleme hepsi için aynı anda olur. Her dal aynı
`cv_processing_workflow`'u çalıştırır. Bu paralel çalışma bir `Parallel` bloğunda
olur:

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
`process` adımıyla aynı çağrıdır. Tekli mod ve toplu mod arasındaki tek fark, bu
çağrının kaç kez ve ne zaman yapıldığıdır (hemen mi, `finalize_batch`'te toplu mu).
Pipeline'ın kendisi değişmez.

**Bilinen bir bedel:** Doğrulama artık `finalize_batch`'e kadar ertelenir. 5
CV'den biri bozuksa, kullanıcı bunu ancak hepsini gönderip `/done` dedikten sonra
öğrenir. Erken geri bildirim yoktur. Bunun karşılığında tek, tutarlı bir pipeline
elde edilir. Bu bilinçli bir karardır (bkz. `ARCHITECTURE.md` §11).

---

## 5. Extraction Agent

**Dosya:** `agents/extraction_agent.py`
**Rolü:** LLM Extraction. Ham, dağınık CV metnini ortak `CandidateProfile` JSON
şemasına normalize eder (ödevin "farklı formatları standartlaştırma" gereksinimi).
**`output_schema`:** `CandidateProfile` (`full_name`, `skills`, `work_experience`,
`languages`, `education`)
**Instructions (özet):** *"Sana verilen ham CV metninden yalnızca açıkça belirtilmiş
bilgileri çıkar. Emin olmadığın alanları boş bırak. Bilgi uydurma."*
**Çağrılma şekli:** `cv_processing_workflow`'un 2. adımıdır — düz bir Agent step.
Tekli mod ve toplu mod bu adımı aynı şekilde çağırır, çünkü ikisi de aynı
workflow'u kullanır.

## 6. Analysis Agent (tekli CV)

**Dosya:** `agents/analysis_agent.py`
**Rolü:** Bir `CandidateProfile` alır, kullanıcının dinamik kriterlerini alır, ve
nitel bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult` (`candidate_name`, `strengths`,
`weaknesses`, `recommendations`, `markdown_report`)
**Instructions (özet):** *"Bir İK uzmanı gibi davran. Sadece verilen kriterlere göre
değerlendir. Kriter dışı özellikleri yorumlama. Güçlü ve zayıf yönleri, ve somut
gelişim tavsiyelerini, Türkçe ve okunaklı bir Markdown raporu olarak üret."*
**Çağrılma şekli:** `single_cv_workflow`'un `analyze_cv` adımından çağrılır. Bu
ajan sadece tekli modda çalışır — toplu mod nitel rapor değil, skor üretir (bkz.
Scoring Agent).

## 7. Scoring Agent (çoklu CV)

**Dosya:** `agents/scoring_agent.py`
**Rolü:** Bir `CandidateProfile` ve dinamik kriter listesini alır. Her kritere ayrı
ayrı 0-100 arası puan verir (ödevin `dynamicScores` alanı).
**`output_schema`:** `CandidateScore` alt kümesi — `dynamicScores: dict[str, int]`,
`hrEvaluation: str` (kısa gerekçe).
**Çağrılma şekli:** `ProcessAndScoreExecutor` içinden çağrılır. `cv_processing_workflow`
bittikten hemen sonra, aynı paralel dal içinde çalışır. Tüm dallar Agno'nun native
`Parallel`'ı ile aynı anda çalışır. Bu proje elle `asyncio.gather`/`Semaphore` yazmaz.
**Sıralama:** `averageScore`, `rank_top3_fn` içinde Python'da hesaplanır. Bu
hesap LLM'e bırakılmaz, çünkü aritmetik ortalama deterministik olmalıdır. İlk 3
aday `rank` alanıyla döner.

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

Tüm ajanlar (Router, Extraction, Analysis, Scoring) modeli bu fabrikadan alır.
Ollama'ya geçiş tek bir env değişkeniyle olur (`MODEL_PROVIDER=ollama`). Bu geçiş
kod değişikliği gerektirmez. **Not:** Ollama'ya geçince, seçilecek modelin
tool-calling ve structured-output desteklemesi gerekir (örnek: `qwen2.5`,
`llama3.1`). Bu not `ARCHITECTURE.md`'de de vardır.

## 9. Session State Şeması (özet — ayrıntı `ARCHITECTURE.md` §4)

```python
{
    "mode": "idle" | "collecting_batch",
    "dynamic_criteria": list[str] | None,
    "batch_files": list[File],   # HAM, işlenmemiş dosyalar — extraction finalize_batch'e ertelenir
}
```
