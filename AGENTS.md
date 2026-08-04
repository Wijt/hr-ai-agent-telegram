# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md`'de tanımlanan sistemin ajan/tool/pipeline envanteri. Bu dosya, her
parçanın *neden var olduğunu*, *ne zaman çağrıldığını* ve *hangi şemayla konuştuğunu*
kayıt altına alır — implementasyon sırasında `src/` altındaki kodun doğrudan
karşılığıdır.

## 0. Çalışma İlkeleri (KISS)

Bu proje üzerinde çalışan herkes (bu oturum dahil, gelecekteki oturumlar dahil)
aşağıdaki ilkelere uyar. Bu bölüm var olduğu için bu ilkeler her seferinde yeniden
anlatılmaz — kod yazmadan önce buraya bakılır.

1. **Keep It Simple, Stupid — ama basitlik tutarlılık demektir, framework'ten kaçınmak
   değil.** Bir CV'yi işlemenin (doğrula → çıkar → bilgi bankasına yaz) tek, paylaşılan
   bir tarifi var: `cv_processing_workflow`. Değerlendirme (tekli ya da çoklu) bu
   bankadan **okuyan** ayrı, tek bir tool (`evaluate_candidates`). İki farklı mimari
   (biri sabit state machine, biri dosya bazlı sorgu) tutmak yerine tek, tutarlı bir
   akış kullanılıyor.
2. **Kompleksite adım adım, gerektikçe eklenir.** En basit çalışan hâliyle başlanır,
   bir sonraki katman ancak bir öncekinin çalıştığı doğrulandıktan sonra eklenir.
   Aşamalı plan için bkz. `ARCHITECTURE.md` §11.
3. **Hello World önce.** (Aşama 0-1 tamamlandı.)
4. **Sektör best practice'i araştırılır, uygulanır.** Kod yazmadan önce Agno'nun resmi
   dokümantasyonu/kurulu paket kaynağı incelenir, oradaki idiom'lar takip edilir.
   Varsayımla ilerlenmez — kurulu pakette (`inspect`/kaynak okuma) doğrulanır.
5. **Sapma gerekiyorsa, önce sorulur.**
6. **Durum yönetimi mümkünse dosya sisteminde tutulur, `session_state`'te değil.**
   Aday bilgi bankası (`data/adaylar/*.md`) kalıcı, sorgulanabilir, ve session'lar
   arası hayatta kalan bir kaynak — bu yüzden kriterler/adaylar için ayrı bir
   `session_state` mekanizması (mod, pending_profile, batch_files vb.) **yok**. Bu,
   önceki bir tasarım turunda (state machine + `set_dynamic_criteria` + `start_batch_session`
   + `finalize_batch`) denenmiş ve kullanıcı geri bildirimiyle bilinçli olarak
   terk edilmiştir.

## Tasarım İlkesi

**Bir router + üç uzman ajan + tek paylaşılan pipeline + dosya tabanlı bilgi bankası:**

- **Router Agent** — Telegram'a bağlı tek ajan. Kullanıcıyla doğrudan konuşan bu. İki
  tool'u var: `submit_cv` (yazan) ve `evaluate_candidates` (okuyan/değerlendiren).
- **`cv_processing_workflow`** — bir CV'yi doğrulama+çıkarmanın tek, paylaşılan tarifi.
- **Bilgi bankası** (`data/adaylar/*.md`) — `cv_processing_workflow`'un ürettiği her
  `CandidateProfile`, insan/LLM okunaklı Markdown olarak buraya yazılır. Bu, hem tekli
  hem çoklu değerlendirmenin **tek ortak veri kaynağı**.
- **`FilesystemContextProvider`** — bu klasörü tarayan, arayan, okuyan hazır Agno
  mekanizması. Biz isim eşleştirme/belirsizlik kodu yazmıyoruz; `evaluate_candidates`
  bunun `query`/`aquery` metodunu doğrudan çağırır (bkz. §3).
- **Extraction / Analysis / Scoring** ajanları LLM tarafından *seçilmez* — sırasıyla
  `cv_processing_workflow`'un bir adımı olarak, ve `evaluate_candidates`'ın içinden
  düz fonksiyon çağrısıyla tetiklenir.

---

## 1. Router Agent

**Dosya:** `src/main.py`
**Bağlı olduğu arayüz:** Agno `Telegram` interface
**Model:** `model_factory.get_model()`
**db:** kendi db'si yok — `AgentOS(db=SqliteDb(...))` seviyesinde tanımlanır, kendi
db'si olmayan her bileşene otomatik atanır.
**`pre_hook`:** o turda ekli dosya (`files`) varsa `tool_choice="submit_cv"` sabitlenir
— dosya geldiğinde `submit_cv`'nin çağrılması LLM kararına değil koda bağlıdır.

**Instructions (özet, Türkçe):**
- Varsayılan davranış: samimi, kısa, bağlamı koruyan bir sohbet asistanı gibi yanıt ver.
- Kullanıcı bir PDF belgesi gönderdiyse → **her zaman** `submit_cv` çağır.
- Kullanıcı bir/birden fazla adayı değerlendirmek/karşılaştırmak istediğini belirtiyorsa
  (kriterleriyle birlikte, örn. *"Ahmet'i React deneyimine göre değerlendir"*,
  *"bu adayları karşılaştır"*) → `evaluate_candidates` çağır; kriterleri ve (varsa)
  aday ipucunu kullanıcının o anki cümlesinden çıkar, argüman olarak geç.
- Kriterleri ayrıca "hatırlamaya" çalışma / saklama — her değerlendirme isteğinde
  kriterler taze olarak argüman olarak gelir.
- Asla CV içeriğini kendi başına yorumlama/skorlama — bu iş uzman ajanlara ait.

**Tool envanteri:**

| Tool | İmza | Ne yapar |
|---|---|---|
| `submit_cv` | `(run_context, files: Optional[Sequence[File]] = None) -> str` | Bkz. §2. Yazan taraf — `cv_processing_workflow`'u çalıştırır, sonucu bilgi bankasına yazar. |
| `evaluate_candidates` | `(run_context, criteria: list[str], scope_hint: str = "") -> str` | Bkz. §3. Okuyan/değerlendiren taraf — bilgi bankasından ilgili adayları bulur, tekli/çoklu dallanır. |

---

## 2. `submit_cv` — Yazan Taraf

```python
async def submit_cv(run_context: RunContext, files: Optional[Sequence[File]] = None) -> str:
    if not files:
        return "Bir PDF dosyası göndermelisin."
    dosya = files[0]

    sonuc = await cv_processing_workflow.arun(files=[dosya])
    if sonuc.step_results[-1].stop:
        return sonuc.content            # PdfValidator hatası, stop=True ile erken bitti

    profile: CandidateProfile = sonuc.content
    yol = write_candidate_markdown(profile, dosya.filename)   # data/adaylar/<slug>.md
    return f"'{profile.full_name or dosya.filename}' bilgi bankasına eklendi."
```

`sonuc.step_results[-1].stop` — Agno'nun `stop=True`'yu sakladığı **gerçek, açık alan**;
elle yazılmış izole bir testle doğrulandı (`step_results[-1].stop == True` durma anında,
`step_results` listesinin uzunluğu da hangi adıma kadar geldiğini gösteriyor — sonraki
adımlar hiç çalışmıyor). `isinstance(content, str)` gibi dolaylı bir tahmine gerek yok;
`RunStatus` her iki durumda da `completed` kaldığı için o alana bakmak yanıltıcı olurdu,
ama `step_results[-1].stop` doğrudan ve güvenilir.

---

## 3. `evaluate_candidates` — Okuyan / Değerlendiren Taraf

```python
async def evaluate_candidates(run_context: RunContext, criteria: list[str], scope_hint: str = "") -> str:
    soru = scope_hint or "Bilgi bankasındaki tüm adayları listele ve her birinin tam içeriğini oku."
    cevap = await candidate_knowledge.aquery(soru)         # FilesystemContextProvider.aquery()
    profiller = load_profiles_from_documents(cevap.results)  # Document.uri -> markdown oku -> CandidateProfile-benzeri metin

    if not profiller:
        return "Bilgi bankasında eşleşen bir aday bulamadım."
    if len(profiller) == 1:
        rapor = await run_single_analysis(profiller[0], criteria)   # analysis_agent çağırır
        return rapor.markdown_report

    return await run_batch_scoring(profiller, criteria)             # Parallel + rank_top3, JSON döner
```

**Kritik tasarım notları:**
- `scope_hint` boşsa "hepsini getir" davranışı; doluysa (`"Ahmet ve Zeynep"` gibi)
  `FilesystemContextProvider`'ın kendi alt-ajanı ilgili dosyaları bulup okur — **biz
  isim eşleştirme/belirsizlik kodu yazmıyoruz**, bu iş Agno'nun hazır mekanizmasında.
- `FilesystemContextProvider.aquery()` bir `Answer(results: list[Document], text: str)`
  döner; `Document.uri`'den dosya yolunu alıp içeriği **düz Python ile** (tam, kesilmemiş)
  okuyoruz — bulma agentic, okuma deterministik.
- 1 profil → nitel analiz (`SingleAnalysisResult.markdown_report`).
- N profil → paralel skorlama + `rank_top3` — bkz. `ARCHITECTURE.md` §6.

---

## 4. Extraction Agent

**Dosya:** `src/agents/extraction_agent.py`
**Rolü:** LLM Extraction — ham CV metnini ortak `CandidateProfile` JSON şemasına
normalize eder.
**`output_schema`:** `CandidateProfile`
**Çağrılma şekli:** `cv_processing_workflow`'un 2. adımı (Agent step).

## 5. Analysis Agent (tekli)

**Dosya:** `src/agents/analysis_agent.py`
**Rolü:** Bir adayın profili + dinamik kriterleri alıp nitel bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult`
**Çağrılma şekli:** `evaluate_candidates` içinden, sadece 1 profil bulunduğunda.

## 6. Scoring Agent (çoklu)

**Dosya:** `src/agents/scoring_agent.py`
**Rolü:** Bir adayın profili + kriter listesini alıp **her kritere ayrı ayrı**
0-100 puan verir.
**`output_schema`:** `CandidateScore` alt kümesi (`dynamicScores`, `hrEvaluation`)
**Çağrılma şekli:** `evaluate_candidates` içinden, N > 1 profil bulunduğunda, her
biri için ayrı bir `Parallel` dalında (Agno native `Parallel`, elle `asyncio.gather`
yazılmıyor).
**Sıralama:** `averageScore` Python'da hesaplanır (LLM'e bırakılmaz), ilk 3 aday
`rank` ile döner.

---

## 7. Model Sağlayıcı Soyutlaması

**Dosya:** `src/models/model_factory.py` (mevcut, değişmedi)

```python
def get_model():
    provider = settings.model_provider  # "openai" (varsayılan) | "ollama"
    if provider == "ollama":
        from agno.models.ollama import Ollama
        return Ollama(id=settings.ollama_model_id, host=settings.ollama_base_url)
    from agno.models.openai import OpenAIChat
    return OpenAIChat(id=settings.openai_model_id)
```

Tüm ajanlar modeli bu fabrikadan alır — Ollama'ya geçiş tek bir env değişkeniyle
yapılır, kod değişikliği gerekmez.

## 8. Kalıcı Durum

`session_state` bu pipeline için **kullanılmıyor** — bkz. §0 madde 6. Tek kalıcı
durum, dosya sisteminde: `data/adaylar/*.md` (aday bilgi bankası) ve
`data/agent-os.db` (Router'ın sohbet geçmişi, Aşama 1).
