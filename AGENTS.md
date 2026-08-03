# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md`'de tanımlanan sistemin ajan/tool/pipeline envanteri. Bu dosya, her
parçanın *neden var olduğunu*, *ne zaman çağrıldığını* ve *hangi şemayla konuştuğunu*
kayıt altına alır — `src/` altındaki düz modüllerin (`bot.py`, `agents.py`,
`workflows.py`) doğrudan karşılığıdır.

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
  Extraction `cv_processing_workflow`'un bir adımı olarak, Analysis `submit_cv`
  tool'unun içinden (workflow bittikten hemen sonra), Scoring `finalize_batch`'in
  paralel dalları içinden çağrılır. Bu ayrım kararlılık için kritik
  (bkz. `ARCHITECTURE.md` §5).

---

## 1. Router Agent

**Dosya:** `bot.py` (`chat_agent`)
**Bağlı olduğu arayüz:** Agno `Telegram` interface (`AgentOS(interfaces=[Telegram(agent=chat_agent)])`)
**Model:** `model_factory.get_model()` (varsayılan OpenAI, env ile Ollama'ya geçer)
**db:** kendi `db`'si yok — `AgentOS(db=SqliteDb(...))` seviyesinde tanımlanır ve
kendi db'si olmayan her agent/workflow'a otomatik atanır (bkz. `ARCHITECTURE.md` §2;
kaynak: `agno/os/app.py`, agent'lar ve workflow'lar için ayrı ayrı doğrulandı).
**Diğer ayarlar:** `send_media_to_model=False`, `store_media=True` — PDF ham içeriği
LLM'e gönderilmez, sadece tool erişimi için saklanır (bkz. `ARCHITECTURE.md` §10.1).
**`pre_hooks=[force_submit_cv_on_file]`:** o turda ekli dosya (`run_input.files`)
varsa `agent.tool_choice` `submit_cv`'ye sabitlenir, yoksa `None`'a geri alınır
(mutasyon Agent nesnesinde kalıcı olduğu için her turda açıkça set edilir — Agno
2.8.6 kaynağından doğrulandı). Dosya geldiğinde `submit_cv`'nin çağrılması böylece
LLM kararına değil koda bağlıdır (bkz. `ARCHITECTURE.md` §5). `submit_cv`'nin
`stop_after_tool_call=True` olması bu zorlamanın yan etkisini de kapatır: zorlanan
tool aynı run içinde tekrar tekrar çağrılamaz (sonsuz döngü koruması) ve dönüşü
LLM'e geri gitmeden kullanıcıya birebir iletilir.

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
| `submit_cv` | `(run_context, criteria: Optional[list[str]] = None, files: Optional[Sequence[File]] = None) -> str` | Bkz. §3. **idle**'da `cv_processing_workflow`'u hemen çalıştırıp `analysis_agent` ile raporlar; (Aşama 3'te) **batch**'te dosyayı işlemeden biriktirir. `criteria` parametresi, kullanıcı dosyayla **aynı mesajda** kriter yazdıysa kaydetmek için (tool_choice zorlandığında `set_dynamic_criteria` çağrılamaz). `files` Agno'nun built-in parametresi — o turun ekli dosyaları otomatik enjekte edilir. `pre_hooks` sayesinde dosya varken çağrılması garanti. `stop_after_tool_call=True`: dönüş kullanıcıya birebir gider. |
| `start_batch_session` *(Aşama 3)* | `(run_context) -> str` | `session_state["mode"] = "collecting_batch"`, `batch_files = []`. Kriter tanımlı değilse kullanıcıyı önce kritere yönlendirir. |
| `finalize_batch` *(Aşama 3)* | `(run_context) -> str` | Bkz. §4. Biriktirilen her dosya için **aynı `cv_processing_workflow`'u paralel olarak** çalıştırır, skorlar, JSON döner, mode'u `idle`'a çeker. |

**Kullanılmayan/gerek olmayan tool'lar:** `reset` — Agno'nun native `/new` komutu
session_state'i zaten sıfırlıyor, tekrar yazılmayacak.

---

## 2. `cv_processing_workflow` — Tek, Paylaşılan Tarif

Bir adayı işlemenin **tek** tanımı. Hem tekli hem toplu mod bunu birebir aynı nesne
olarak kullanır — biri bir kez, öbürü N kez paralel:

**Dosya:** `workflows.py` — gerçek kod:

```python
def validate_pdf_step(step_input: StepInput) -> StepOutput:
    files = step_input.files or []
    if not files:  # Telegram 20MB üzeri dosyayı hiç indirmez
        return StepOutput(content="Dosyayı alamadım. 20MB'tan küçük bir PDF dener misin?", stop=True)
    raw = files[0].content if isinstance(files[0].content, bytes) else b""
    text, error = validate_pdf(raw)              # bkz. ARCHITECTURE.md §9 — LLM'siz
    if error:
        return StepOutput(content=error, stop=True)   # resmi early-stop deseni; extract hiç çalışmaz
    return StepOutput(content=text)

cv_processing_workflow = Workflow(
    name="CV Processing",
    steps=[
        Step(name="validate_pdf", executor=validate_pdf_step),
        Step(name="extract_cv", agent=extraction_agent),   # -> CandidateProfile (output_schema)
        # Aşama 4'te (opsiyonel): Step(name="store_to_knowledge", executor=...)
    ],
)
```

`extract_cv` çıktısı (`CandidateProfile`, **tipli Pydantic nesnesi** — Agno string'e
çevirmiyor, kaynak + canlı testle doğrulandı) → `run_output.content` olarak çağırana
döner. Erken durmayı çağıran `workflows.stopped_early(run_output)` ile anlar
(`step_results[-1].stop` — Agno'da bunun için ayrı bir alan yok).

---

## 3. Tekli Mod — `submit_cv` (bot.py)

**KISS revizyonu (kullanıcı kararı):** başlangıç tasarımındaki sarmalayıcı
`single_cv_workflow` kaldırıldı. Tekli mod, `submit_cv` tool'unun içinde iki düz
çağrıdır — bu, Aşama 3'ün toplu deseniyle (**workflow + tek uzman ajan çağrısı**)
birebir aynı şekildir, ekstra bir workflow katmanı hem gereksizdi hem iki modu
farklılaştırıyordu:

```python
@tool(stop_after_tool_call=True)  # dönüş LLM'e geri gitmez, olduğu gibi kullanıcıya iletilir
def submit_cv(run_context, criteria=None, files=None):
    if not files:
        return "Analiz için bir PDF dosyası göndermelisin."
    if criteria:  # dosyayla aynı mesajda kriter yazıldıysa (tool_choice zorlanmışken tek şans)
        run_context.session_state["dynamic_criteria"] = criteria
    criteria = run_context.session_state.get("dynamic_criteria")
    if not criteria:
        return "Bu CV'yi hangi kriterlere göre değerlendirmemi istersin? ..."

    run = cv_processing_workflow.run(files=list(files))     # TEK paylaşılan tarif
    if stopped_early(run):
        return str(run.content)                             # validate_pdf'in hata mesajı, birebir
    profile = run.content                                   # CandidateProfile (tipli)
    if not isinstance(profile, CandidateProfile):
        return f"CV işlenirken beklenmedik bir sorun oluştu: {profile}"

    analiz = analysis_agent.run(f"Aday profili (JSON):\n{profile.model_dump_json()}\n\nKriterler: {', '.join(criteria)}")
    return analiz.content.markdown_report                   # SingleAnalysisResult
```

**Asenkronluk notu:** `submit_cv` bilinçli olarak **sync** — Agno, async agent run
içindeki sync tool'ları `asyncio.to_thread` ile ayrı thread'e atar (kaynaktan
doğrulandı), yani uzun süren workflow koşusu event loop'u ve diğer Telegram
mesajlarını bloklamaz. Tool'u `async def` yapıp içinde sync `workflow.run()`
çağırmak ise loop'u kilitlerdi — bu tuzağa düşülmedi.

---

## 4. Toplu Mod — `finalize_batch`: Aynı Tarifi N Kez, Paralel

Toplu mod, `submit_cv` sırasında **hiçbir şey işlemez** — sadece ham dosyaları
biriktirir (bkz. §3). Tüm işleme (doğrulama + çıkarım + skorlama), `finalize_batch`
çağrıldığında **hepsi aynı anda**, her biri **aynı `cv_processing_workflow`'u**
çalıştıran bir `Parallel` bloğunda yapılır:

```python
def make_process_and_score(file: File, criteria: list[str]):
    """Her paralel dal için bir closure üretir (class değil — KISS). Dal kendi
    dosyasını/kriterini taşır ama hepsi AYNI cv_processing_workflow nesnesini çağırır."""

    async def process_and_score(step_input: StepInput) -> StepOutput:
        sonuc = await cv_processing_workflow.arun(files=[file])   # <-- tekli modla BİREBİR aynı çağrı
        if stopped_early(sonuc):
            return StepOutput(content={"filename": file.filename, "error": str(sonuc.content)}, success=False)
        profile = sonuc.content                                   # CandidateProfile
        skor = await scoring_agent.arun(
            f"Aday profili: {profile.model_dump_json()}\nKriterler: {criteria}"
        )
        return StepOutput(content={"filename": file.filename, "profile": profile, "score": skor.content})

    return process_and_score


def finalize_batch(run_context):
    if session_state["mode"] != "collecting_batch":
        return "Şu an toplanan bir CV grubu yok."
    if not session_state["batch_files"]:
        return "Henüz hiç CV göndermedin."

    criteria = session_state["dynamic_criteria"]
    branches = [
        Step(name=f"candidate_{i}", executor=make_process_and_score(file, criteria))
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

**Bu tasarımın kilit noktası:** `process_and_score` içindeki
`cv_processing_workflow.arun(files=[file])` satırı, tekli modda `submit_cv`'nin
yaptığı **birebir aynı çağrı**; ikisi de ardından tek bir uzman ajan (Analysis /
Scoring) çağırır. Tekli/toplu arasındaki tek fark, kaç kez ve ne zaman (hemen mi,
`finalize_batch`'te toplu mu) çağrıldığı — pipeline'ın kendisi değil.

**Bilinen trade-off:** Doğrulama artık `finalize_batch`'e kadar ertelendiği için,
5 CV'den biri bozuksa kullanıcı bunu ancak hepsini gönderip `/done` dedikten sonra
öğrenir (erken geri bildirim yok). Bunun karşılığında tek, tutarlı bir pipeline elde
ediyoruz — bilinçli bir tercih, `ARCHITECTURE.md` §11'de kayıtlı.

---

## 5. Extraction Agent

**Dosya:** `agents.py` (`extraction_agent`)
**Rolü:** LLM Extraction — ham, dağınık CV metnini ortak `CandidateProfile` JSON
şemasına normalize eder (ödevin "farklı formatları standartlaştırma" gereksinimi).
**`send_media_to_model=False`:** workflow dosyaları her adıma taşıdığı için PDF
baytlarının modele multimodal gitmesi bu bayrakla kapatıldı — girdisi yalnızca
`validate_pdf_step`'in çıkardığı düz metin.
**`output_schema`:** `CandidateProfile` (`full_name`, `skills`, `work_experience`,
`languages`, `education`)
**Instructions (özet):** *"Sana verilen ham CV metninden yalnızca açıkça belirtilmiş
bilgileri çıkar. Emin olmadığın alanları boş bırak, uydurma."*
**Çağrılma şekli:** `cv_processing_workflow`'un 2. adımı — düz bir Agent step.
Hem tekli hem toplu modda **aynı şekilde** çağrılır çünkü ikisi de aynı workflow'u
kullanır.

## 6. Analysis Agent (tekli CV)

**Dosya:** `agents.py` (`analysis_agent`)
**Rolü:** Tek bir `CandidateProfile` + kullanıcının dinamik kriterlerini alıp nitel
bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult` (`candidate_name`, `strengths`,
`weaknesses`, `recommendations`, `markdown_report`)
**Instructions (özet):** *"Bir İK uzmanı gibi davran. Sadece verilen kriterlere göre
değerlendir, kriter dışı özellikleri yorumlama. Güçlü/zayıf yönleri ve somut gelişim
tavsiyelerini Türkçe, okunaklı bir Markdown raporu olarak üret."*
**Çağrılma şekli:** `bot.submit_cv` içinden, `cv_processing_workflow` başarıyla
bittikten hemen sonra. Sadece tekli modda kullanılır — toplu mod nitel rapor değil,
skor üretir (bkz. Scoring Agent).

## 7. Scoring Agent (çoklu CV)

**Dosya:** `agents.py` (`scoring_agent` — Aşama 3'te eklenecek)
**Rolü:** Bir `CandidateProfile` + dinamik kriter listesini alıp **her kritere ayrı
ayrı 0-100 arası puan** verir (ödevin `dynamicScores` alanı).
**`output_schema`:** `CandidateScore` alt kümesi — `dynamicScores: dict[str, int]`,
`hrEvaluation: str` (kısa gerekçe).
**Çağrılma şekli:** `process_and_score` closure'ı içinden, `cv_processing_workflow`
tamamlandıktan **hemen sonra**, aynı paralel dal içinde. Tüm dallar Agno'nun native
`Parallel`'ı ile aynı anda çalışır — elle `asyncio.gather`/`Semaphore` yazılmıyor.
**Sıralama:** `averageScore` `rank_top3_fn` içinde Python'da hesaplanır (LLM'e
bırakılmaz — aritmetik ortalama deterministik olmalı), ilk 3 aday `rank` ile döner.

---

## 8. Model Sağlayıcı Soyutlaması

**Dosya:** `model_factory.py`

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
# Aşama 2 (mevcut): sadece kullanılan anahtar tanımlı — "kompleksite gerektikçe"
{
    "dynamic_criteria": list[str] | None,
}
# Aşama 3'te eklenecek:
#   "mode": "idle" | "collecting_batch",
#   "batch_files": list[File],   # HAM dosyalar — extraction finalize_batch'e ertelenir
```

Başlangıç değeri `Agent(session_state={...})` ile verilir; Agno yeni her session'a
bunun deepcopy'sini atar, tool'ların `run_context.session_state` mutasyonlarını run
sonunda SqliteDb'ye persist eder (öncelik: run parametresi > db > agent varsayılanı).
