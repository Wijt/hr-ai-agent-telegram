# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md`'de tanımlanan sistemin ajan/tool/süreç envanteri. Bu dosya, her
parçanın *neden var olduğunu*, *ne zaman çağrıldığını* ve *hangi şemayla konuştuğunu*
kayıt altına alır — implementasyon sırasında `src/` altındaki kodun doğrudan
karşılığıdır.

## 0. Çalışma İlkeleri (KISS)

Bu proje üzerinde çalışan herkes (bu oturum dahil, gelecekteki oturumlar dahil)
aşağıdaki ilkelere uyar. Bu bölüm var olduğu için bu ilkeler her seferinde yeniden
anlatılmaz — kod yazmadan önce buraya bakılır.

1. **Keep It Simple, Stupid — ama basitlik tutarlılık demektir, framework'ten kaçınmak
   değil.** Bir CV'yi işlemenin (doğrula → çıkar → bilgi bankasına yaz) tek, paylaşılan
   bir tarifi var: `cv_intake.process_cv` — düz bir fonksiyon, çünkü iki adım hep aynı
   sırada çalışıyor ve tek erken-çıkış koşulu var; `Workflow` burada gereksiz ağırlıktı
   (bkz. `ARCHITECTURE.md` §6, §9.2 — bir turda denenip geri alındı). Değerlendirme
   (tekli ya da çoklu) bu bankadan **okuyan** ayrı bir modül (`candidate_analysis`),
   tek bir tool (`evaluate_candidates`) üzerinden. İki farklı mimari (biri sabit state
   machine, biri dosya bazlı sorgu) tutmak yerine tek, tutarlı bir akış kullanılıyor.
2. **Kod, teknik katmana değil sürece göre organize edilir.** Tek proje, tek HR agent;
   `src/domain/`, `src/services/`, `src/agents/`, `src/workflows/` gibi katman bazlı
   alt paketler **kullanılmaz** — bu, kullanıcı geri bildirimiyle iki kez bilinçli
   olarak terk edildi. Somut kurallar:
   - `__init__.py` yok, iç içe paket yok — `src/` düz: `main.py`, `config.py`,
     `model_factory.py`, `models.py`, `pdf_validator.py`, `candidate_store.py`,
     `cv_intake.py`, `candidate_analysis.py`.
   - Tek bir fonksiyonu sarmalamak için class yazılmaz. Kapatılması gereken durum
     (closure state) varsa düz bir iç içe fonksiyon kullanılır (örn.
     `candidate_analysis._score_step`), `__init__`+`__call__`'lı bir class değil.
   - Sonuç/hata ayrımı mümkünse tuple ile (`(profile, None)` / `(None, hata_mesajı)`),
     `isinstance` ile tahmin yürütülmez.
   - Testler minimal: senaryo başına 1 kısa test, `conftest.py`/`sys.path` hack'i
     yerine kök dizindeki `pytest.ini` (`pythonpath = src`).
3. **Kompleksite adım adım, gerektikçe eklenir.** En basit çalışan hâliyle başlanır,
   bir sonraki katman ancak bir öncekinin çalıştığı doğrulandıktan sonra eklenir.
   Aşamalı plan için bkz. `ARCHITECTURE.md` §13.
4. **Hello World önce.** (Aşama 0-1 tamamlandı.)
5. **Sektör best practice'i araştırılır, uygulanır.** Kod yazmadan önce Agno'nun resmi
   dokümantasyonu/kurulu paket kaynağı incelenir, oradaki idiom'lar takip edilir.
   Varsayımla ilerlenmez — kurulu pakette (`inspect`/kaynak okuma) doğrulanır.
6. **Sapma gerekiyorsa, önce sorulur.**
7. **Durum yönetimi mümkünse dosya sisteminde tutulur, `session_state`'te değil.**
   Aday bilgi bankası (`data/adaylar/*.md`) kalıcı, sorgulanabilir, ve session'lar
   arası hayatta kalan bir kaynak — bu yüzden kriterler/adaylar için ayrı bir
   `session_state` mekanizması (mod, pending_profile, batch_files vb.) **yok**. Bu,
   önceki bir tasarım turunda (state machine + `set_dynamic_criteria` + `start_batch_session`
   + `finalize_batch`) denenmiş ve kullanıcı geri bildirimiyle bilinçli olarak
   terk edilmiştir.

## Tasarım İlkesi

**Bir router + iki süreç modülü + dosya tabanlı bilgi bankası:**

- **Router Agent** — Telegram'a bağlı tek ajan. Kullanıcıyla doğrudan konuşan bu. İki
  tool'u var: `submit_cv` (intake'i tetikler) ve `evaluate_candidates` (analizi tetikler).
- **`cv_intake.process_cv`** — bir CV'yi doğrulama+çıkarmanın tek, paylaşılan tarifi.
- **Bilgi bankası** (`data/adaylar/*.md`) — `process_cv`'nin ürettiği her
  `CandidateProfile`, insan/LLM okunaklı Markdown olarak `candidate_store.py`
  üzerinden buraya yazılır. Bu, hem tekli hem çoklu değerlendirmenin **tek ortak
  veri kaynağı**.
- **`candidate_store.find_candidates_by_hint`** — bu klasörü tarayan, `scope_hint`
  kelimeleriyle aday adları arasında önek eşleşmesi arayan, LLM'siz fonksiyon (bkz.
  §3). `FilesystemContextProvider` denendi, canlı testte `Answer.results` boş
  döndü (`ARCHITECTURE.md` §9.3) — deterministik eşleşmeye geçildi.
- **Extraction / Analysis / Scoring** ajanları LLM tarafından *seçilmez* — sırasıyla
  `cv_intake.process_cv`'nin içinden, ve `candidate_analysis`'ın
  `analyze_single`/`analyze_batch` fonksiyonlarından düz çağrıyla tetiklenir.

---

## 1. Router Agent

**Dosya:** `src/main.py`
**Bağlı olduğu arayüz:** Agno `Telegram` interface
**Model:** `model_factory.get_model()`
**db:** kendi db'si yok — `AgentOS(db=SqliteDb(...))` seviyesinde tanımlanır, kendi
db'si olmayan her bileşene otomatik atanır.
**`pre_hook`:** o turda ekli dosya (`files`) varsa `tool_choice="submit_cv"` sabitlenir
— dosya geldiğinde `submit_cv`'nin çağrılması LLM kararına değil koda bağlıdır. Dosya
yoksa `"auto"`'ya döner (agent nesnesi turlar arası paylaşıldığı için, önceki turdan
kalmasın diye).

**Instructions (özet, Türkçe) — canlı testte bulunan bir routing hatasından sonra
üç net dala ayrıldı:**
- Varsayılan davranış: samimi, kısa, bağlamı koruyan bir sohbet asistanı gibi yanıt ver.
- Kullanıcı bir PDF belgesi gönderdiyse (bu mesajda **yeni** dosya ekliyse) → **her
  zaman** `submit_cv` çağır. Yeni dosya yoksa `submit_cv` **asla** çağrılmaz — "bu CV",
  "bu aday" gibi ifadeler zaten yüklenmiş bir CV'ye atıftır, yeni dosya değil.
- Kullanıcı **somut kriterler belirterek** bir/birden fazla adayı değerlendirmek/
  karşılaştırmak istediğinde → `evaluate_candidates` çağır; kriterleri ve (varsa)
  aday ipucunu kullanıcının o anki cümlesinden çıkar, argüman olarak geç. Kriterleri
  ayrıca "hatırlamaya" çalışma — her istekte taze gelir.
- Kullanıcı değerlendirme istiyor ama **henüz kriter belirtmediyse** (örn. "genel
  değerlendirme yap") → hiçbir tool çağırma, önce hangi kritere göre bakmam
  gerektiğini sor.
- Asla CV içeriğini kendi başına yorumlama/skorlama — bu iş uzman ajanlara ait.

**Tool envanteri:**

| Tool | İmza | Ne yapar |
|---|---|---|
| `submit_cv` | `(run_context, files: Optional[Sequence[File]] = None) -> str`, `@tool(stop_after_tool_call=True)` | Bkz. §2. `cv_intake.process_cv`'yi çalıştırır, sonucu bilgi bankasına yazar. |
| `evaluate_candidates` | `(run_context, criteria: list[str], scope_hint: str = "") -> str` | Bkz. §3. Bilgi bankasından ilgili adayları bulur, tekli/çoklu dallanır. |

---

## 2. `submit_cv` — Intake Tetikleyici

```python
@tool(stop_after_tool_call=True)
async def submit_cv(run_context: RunContext, files: Optional[Sequence[File]] = None) -> str:
    if not files:
        return "Değerlendirmemi istiyorsan hangi kriterlere göre bakmamı istediğini söyle; ..."
    dosya = files[0]

    profile, error = await cv_intake.process_cv(dosya)
    if error:
        return error            # PdfValidator hatası

    candidate_store.write_candidate_markdown(profile, dosya.filename or "cv.pdf")
    return f"'{profile.full_name or dosya.filename}' bilgi bankasına eklendi."
```

**`@tool(stop_after_tool_call=True)` kritik:** bunsuz, `pre_hook`'un zorladığı
`tool_choice`, run içindeki HER model çağrısında yeniden okunuyor (`agno/agent/_run.py`
— sadece ilk çağrıda değil). Yani tool sonucunu özetleyecek bir sonraki model çağrısı
da `submit_cv`'yi çağırmaya zorlanır ve sonsuz döngüye girer — canlı testte tam olarak
bu görüldü. `stop_after_tool_call=True` ile `show_result` otomatik `True` olur: run,
tool'un dönüş değerini LLM'e yeniden yorumlatmadan **aynen** kullanıcıya iletip biter
(kaynak: `agno/models/base.py`, `show_result` → `ModelResponse(content=function_call_output)`)
— hem döngüyü öldürür hem "eklendi" onayının gerçekten session history'e (ve kullanıcıya)
ulaşmasını garanti eder.

`process_cv`'nin `(profile, error)` tuple dönüşü, önceki bir turda yaşanan bir hataya
karşı bilinçli: eski kod `Workflow` çıktısını `isinstance(content, str)` ile
yorumluyordu ("str dönerse hata" gibi dolaylı bir tahmin) — bu yanlıştı. Tuple, hangi
dalın gerçekleştiğini açık bırakır.

---

## 3. `evaluate_candidates` — Analiz Tetikleyici

```python
async def evaluate_candidates(run_context: RunContext, criteria: list[str], scope_hint: str = "") -> str:
    if not criteria:
        return "Hangi kriterlere göre değerlendirmemi istersin?"   # kod seviyesinde güvenlik ağı

    if scope_hint:
        docs = candidate_store.find_candidates_by_hint(scope_hint)   # önek eşleşmesi, LLM'siz
    else:
        docs = candidate_store.list_all_candidates()                 # deterministik glob

    if not docs:
        return "Bilgi bankasında eşleşen bir aday bulamadım."
    if len(docs) == 1:
        return await candidate_analysis.analyze_single(docs[0], criteria)

    return await candidate_analysis.analyze_batch(docs, criteria)
```

**Kritik tasarım notları:**
- `criteria` boşsa **hiçbir arama/LLM çağrısı yapılmadan** kriter sorulur — canlı
  testte router'ın kriter yokken yanlışlıkla `submit_cv`'yi çağırdığı görüldü; bu,
  instructions'taki (§1) düzeltmeye ek bir kod seviyesi güvenlik ağı.
- `scope_hint` boşsa (en yaygın senaryo, "bunları karşılaştır") bilgi bankası
  tamamen deterministik okunur (`list_all_candidates`); doluysa (`"Ahmet"` gibi)
  `find_candidates_by_hint` kelime-önek karşılaştırmasıyla filtreler (Türkçe hâl
  eklerini tolere eder: "Ahmet" ~ "Ahmet'i") — LLM'siz, isim eşleştirme kodu
  gerektiği ortaya çıktı (`FilesystemContextProvider` bunu üstlenecekti ama canlı
  testte güvenilmez çıktı, `ARCHITECTURE.md` §9.3).
- Bulunan dosyaların **tam içeriği** her koşulda düz Python ile (`Path.read_text()`)
  okunur — kesilmiş bir özete güvenilmez, yargılama tam metinle yapılır.
- 1 profil → nitel analiz (`SingleAnalysisResult.markdown_report`).
- N profil → paralel skorlama + sıralama — bkz. `ARCHITECTURE.md` §6.

---

## 4. Extraction Agent

**Dosya:** `src/cv_intake.py`
**Rolü:** LLM Extraction — ham CV metnini ortak `CandidateProfile` JSON şemasına
normalize eder.
**`output_schema`:** `CandidateProfile`
**Çağrılma şekli:** `process_cv`'nin 2. adımı, doğrulama başarılı olduktan sonra.

## 5. Analysis Agent (tekli)

**Dosya:** `src/candidate_analysis.py`
**Rolü:** Bir adayın profili + dinamik kriterleri alıp nitel bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult`
**Çağrılma şekli:** `analyze_single`, sadece 1 profil bulunduğunda.

## 6. Scoring Agent (çoklu)

**Dosya:** `src/candidate_analysis.py`
**Rolü:** Bir adayın profili + kriter listesini alıp **her kritere ayrı ayrı**
0-100 puan verir.
**`output_schema`:** `CriterionScores` (`dynamic_scores`, `hr_evaluation`)
**Çağrılma şekli:** `analyze_batch` içinden, N > 1 profil bulunduğunda, her biri için
ayrı bir `Parallel` dalında (Agno native `Parallel`, elle `asyncio.gather` yazılmıyor
— burada `Workflow` gerçekten gerekli, bkz. `ARCHITECTURE.md` §6 madde 7).
Her dal, `_score_step` adlı bir closure-üreten fonksiyondan gelir (class değil).
**Sıralama:** `averageScore` Python'da hesaplanır (LLM'e bırakılmaz), ilk 3 aday
`rank` ile döner — `_rank_step`, `Parallel`'in tüm dal çıktılarını
`step_input.get_step_content(isim)` ile isim isim toplar.

---

## 7. Model Sağlayıcı Soyutlaması

**Dosya:** `src/model_factory.py`

```python
def get_model():
    provider = settings.model_provider  # "openai" (varsayılan) | "ollama"
    if provider == "ollama":
        from agno.models.ollama import Ollama
        return Ollama(id=settings.ollama_model_id, host=settings.ollama_base_url)
    from agno.models.openai import OpenAIChat
    return OpenAIChat(id=settings.openai_model_id, reasoning_effort=settings.openai_reasoning_effort)
```

Tüm ajanlar modeli bu fabrikadan alır — Ollama'ya geçiş tek bir env değişkeniyle
yapılır, kod değişikliği gerekmez. `reasoning_effort`, `OPENAI_REASONING_EFFORT` env
değişkeniyle kontrol edilir (boşsa gönderilmez) — reasoning modelleri (gpt-5.x gibi)
tool'larla `/v1/chat/completions` üzerinde bunu zorunlu `"none"` ister, aksi halde
400 hatası verir; canlı testte bu hata görülüp düzeltildi.

## 8. Kalıcı Durum

`session_state` bu pipeline için **kullanılmıyor** — bkz. §0 madde 7. Tek kalıcı
durum, dosya sisteminde: `data/adaylar/*.md` (aday bilgi bankası) ve
`data/agent-os.db` (Router'ın sohbet geçmişi, Aşama 1).

**Yol çözümü cwd'ye değil dosya konumuna göre** (`Path(__file__).resolve().parent.parent
/ "data"`), göreli bir yol değil — canlı testte botun hangi dizinden başlatıldığına
bağlı olarak iki farklı, birbirinden habersiz `data/` klasörü oluştuğu görüldü
(`ARCHITECTURE.md` §9.4).
