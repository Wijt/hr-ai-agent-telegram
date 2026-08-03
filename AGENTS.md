# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md`'de tanımlanan sistemin ajan/tool/workflow envanteri. Bu dosya, her
parçanın *neden var olduğunu*, *ne zaman çağrıldığını* ve *hangi şemayla konuştuğunu*
kayıt altına alır — implementasyon sırasında `src/hrbot/agents/` ve
`src/hrbot/workflows/` altındaki kodun doğrudan karşılığıdır.

## Tasarım İlkesi

Tek bir "her şeyi yapan" ajan yerine, **bir router + üç uzman ajan + üç Workflow** modeli:

- **Router Agent** — Telegram'a bağlı tek ajan. Kullanıcıyla doğrudan konuşan bu.
  Kendi başına CV analiz etmez; ne zaman hangi Workflow'un devreye gireceğine
  tool-calling ile karar verir.
- **Extraction / Analysis / Scoring** ajanları LLM tarafından *seçilmez* — bir
  Workflow'un adımı olarak (Agent step ya da function-executor içinden) çağrılır.
- **Workflow'lar** (`cv_intake_workflow`, `single_cv_workflow`, `batch_scoring_workflow`)
  bu üç ajanı ve `PdfValidator` servisini **sabit, kod tanımlı bir sırada** birbirine
  bağlar. Bu ayrım kararlılık için kritik (bkz. `ARCHITECTURE.md` §5, §6).

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
  verme, tool zaten mevcut duruma göre doğru Workflow'u tetikleyecek).
- Kullanıcı `/done` yazdıysa → `finalize_batch` çağır.
- Asla CV içeriğini kendi başına yorumlama/skorlama — bu iş Workflow'ların içindeki
  uzman ajanlara ait.

**Tool envanteri:**

| Tool | İmza | Ne yapar |
|---|---|---|
| `set_dynamic_criteria` | `(run_context, criteria: list[str]) -> str` | Kullanıcının serbest metnini LLM zaten tool-call argümanı olarak listeye çevirir; `session_state["dynamic_criteria"]` güncellenir. |
| `start_batch_session` | `(run_context) -> str` | `session_state["mode"] = "collecting_batch"`, `batch_cvs = []`. Kriter tanımlı değilse kullanıcıyı önce kritere yönlendirir. |
| `submit_cv` | `(run_context, files: Optional[Sequence[File]] = None) -> str` | Bkz. §2. Mod'a göre `single_cv_workflow` ya da `cv_intake_workflow`'u çalıştırır. `pre_hook` sayesinde dosya varken çağrılması garanti. |
| `finalize_batch` | `(run_context) -> str` | Bkz. §3. `batch_scoring_workflow`'u çalıştırır, JSON döner, mode'u `idle`'a çeker. |

**Kullanılmayan/gerek olmayan tool'lar:** `reset` — Agno'nun native `/new` komutu
session_state'i zaten sıfırlıyor, tekrar yazılmayacak.

---

## 2. `submit_cv` — Workflow Tetikleme Mantığı

Bu, Router'ın en kritik tool'u; LLM sadece *"bir CV geldi, bunu çağır"* kararını
verir, gerisi ilgili Workflow'a devredilir:

```
submit_cv(run_context, files):
    # files: Agno tarafından otomatik enjekte edilir (built-in tool parametresi)
    # pre_hook zaten dosya varken bu tool'un çağrılmasını garanti ediyor
    if not files:
        return "Bir PDF dosyası göndermelisin."

    criteria = session_state["dynamic_criteria"]

    if session_state["mode"] == "collecting_batch":
        if not criteria:
            return "Önce kriterleri tanımlamalısın."

        sonuc = cv_intake_workflow.run(files=files)      # validate_pdf -> extract_cv
        if sonuc.stopped:                                 # validate_pdf stop=True döndüyse
            return sonuc.content                           # kullanıcıya net hata mesajı

        session_state["batch_cvs"].append((sonuc.content, files[0].filename))  # sonuc.content: CandidateProfile
        if len(batch_cvs) == 5:
            return finalize_batch(run_context)             # otomatik tetikleme
        return f"{len(batch_cvs)}/5 CV alındı. Daha fazla gönder ya da /done yaz."

    else:  # idle -> tekli analiz
        if not criteria:
            return "Bu CV'yi hangi kriterlere göre değerlendirmemi istersin?"

        sonuc = single_cv_workflow.run(
            input=json.dumps({"criteria": criteria}),
            files=files,
        )
        if sonuc.stopped:
            return sonuc.content                            # validate_pdf hatası
        return sonuc.content.markdown_report                 # SingleAnalysisResult
```

`cv_intake_workflow` hem batch modda (yukarıda doğrudan) hem `single_cv_workflow`'un
ilk adımı olarak (aşağıda, iç içe workflow-as-step ile) kullanılır — kod tekrarı yok.

---

## 3. `finalize_batch` — Paralel Skorlama Tetikleme

```
finalize_batch(run_context):
    if session_state["mode"] != "collecting_batch":
        return "Şu an toplanan bir CV grubu yok."
    if not session_state["batch_cvs"]:
        return "Henüz hiç CV göndermedin."

    # Her aday için ayrı bir class-based executor örneği — kendi CandidateProfile'ını
    # ve pdfFileName'ini closure'da taşır (bkz. ARCHITECTURE.md §6, madde 5)
    branches = [
        Step(name=f"score_{i}", executor=ScoreCvExecutor(profile, filename))
        for i, (profile, filename) in enumerate(session_state["batch_cvs"])
    ]

    workflow = Workflow(steps=[
        Parallel(*branches, name="score_all"),
        Step(name="rank_top3", executor=rank_top3_fn),
    ])
    sonuc = workflow.run(input=json.dumps({"criteria": session_state["dynamic_criteria"]}))

    session_state["mode"] = "idle"
    session_state["batch_cvs"] = []
    return sonuc.content   # BatchAnalysisResult (JSON)
```

`batch_scoring_workflow` her çağrıda **dinamik olarak** kurulur (branch sayısı toplanan
CV sayısına bağlı, 2-5 arası) — Agno `Workflow(steps=[...])` bunu bir Python listesi
olarak kabul ettiği için sorun değil.

---

## 4. Extraction Agent

**Dosya:** `agents/extraction_agent.py`
**Rolü:** LLM Extraction — ham, dağınık CV metnini ortak `CandidateProfile` JSON
şemasına normalize eder (ödevin "farklı formatları standartlaştırma" gereksinimi).
**`output_schema`:** `CandidateProfile` (`full_name`, `skills`, `work_experience`,
`languages`, `education`)
**Instructions (özet):** *"Sana verilen ham CV metninden yalnızca açıkça belirtilmiş
bilgileri çıkar. Emin olmadığın alanları boş bırak, uydurma."*
**Çağrılma şekli:** `cv_intake_workflow`'un 2. adımı — düz bir Agent step
(`Step(name="extract_cv", agent=extraction_agent)`). `validate_pdf`'in çıkardığı
metni otomatik olarak `previous_step_content` üzerinden alır.

## 5. Analysis Agent (tekli CV)

**Dosya:** `agents/analysis_agent.py`
**Rolü:** Tek bir `CandidateProfile` + kullanıcının dinamik kriterlerini alıp nitel
bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult` (`candidate_name`, `strengths`,
`weaknesses`, `recommendations`, `markdown_report`)
**Instructions (özet):** *"Bir İK uzmanı gibi davran. Sadece verilen kriterlere göre
değerlendir, kriter dışı özellikleri yorumlama. Güçlü/zayıf yönleri ve somut gelişim
tavsiyelerini Türkçe, okunaklı bir Markdown raporu olarak üret."*
**Çağrılma şekli:** `single_cv_workflow`'un 3. adımı — **function-executor**
(`analyze_cv_step`). Bu adım hem `step_input.previous_step_content`'ten
`CandidateProfile`'ı hem `step_input.get_input_as_string()`'ten dinamik kriterleri
okur, ikisini birleştirip `analysis_agent.run(...)`'ı kendisi çağırır, sonucu
`StepOutput(content=...)` olarak sarar. Agent step değil, çünkü tek bir kaynaktan
(sadece `previous_step_content`) beslenmiyor.

## 6. Scoring Agent (çoklu CV)

**Dosya:** `agents/scoring_agent.py`
**Rolü:** Bir `CandidateProfile` + dinamik kriter listesini alıp **her kritere ayrı
ayrı 0-100 arası puan** verir (ödevin `dynamicScores` alanı).
**`output_schema`:** `CandidateScore` alt kümesi — `dynamicScores: dict[str, int]`,
`hrEvaluation: str` (kısa gerekçe).
**Çağrılma şekli:** `batch_scoring_workflow`'un `Parallel` bloğu içinde, her aday
için ayrı bir `ScoreCvExecutor(profile, filename)` **class-based executor** örneği
olarak (bkz. `ARCHITECTURE.md` §6, madde 5, §8). Tüm dallar Agno'nun native
`Parallel`'ı ile **aynı anda** çalışır — elle `asyncio.gather`/`Semaphore` yazılmıyor.
**Sıralama:** `averageScore` `rank_top3_fn` içinde Python'da hesaplanır (LLM'e
bırakılmaz — aritmetik ortalama deterministik olmalı), ilk 3 aday `rank` ile döner.

---

## 7. Model Sağlayıcı Soyutlaması

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

## 8. Session State Şeması (özet — detay `ARCHITECTURE.md` §4)

```python
{
    "mode": "idle" | "collecting_batch",
    "dynamic_criteria": list[str] | None,
    "batch_cvs": list[tuple[CandidateProfile, pdf_file_name: str]],
}
```
