# Devir Notu / TODO — telegram-ai-hr-bot

Bu dosya, farklı bir Claude Code oturumuna geçilirken bağlamın kaybolmaması için
yazıldı. **Yeni oturum kod yazmaya başlamadan önce sırasıyla şunları okumalı:**

1. Bu dosya (özet + operasyonel bilgi + somut sıradaki adımlar)
2. `AGENTS.md` §0 — çalışma ilkeleri (KISS, aşamalı geliştirme, best-practice
   zorunluluğu). **Bunlara uyulmadan yazılan kod muhtemelen geri alınacaktır.**
3. `ARCHITECTURE.md` — tüm mimari kararlar ve *neden* öyle karar verildiği
4. `AGENTS.md` §1'den itibaren — ajan/tool/pipeline'ların kod karşılığı

Aşağıdakiler bu üç dosyada **olmayan**, sadece bu oturumda öğrenilen/kurulan/
tartışılan ama henüz kalıcı hale getirilmemiş bilgiler.

## 1. Şu anki durum

- **Aşama 0 — Hello World: ✅ tamamlandı, gerçek Telegram botuyla doğrulandı.**
- **Aşama 1 — Sohbet + session (SqliteDb): ✅ tamamlandı ve doğrulandı.**
- **Aşama 2 — Bilgi bankası + Değerlendirme: ✅ kod olarak TAMAMLANDI**, ama
  **henüz gerçek bir OpenAI API key ile canlı test edilmedi.** Mimari, bu
  dosyanın önceki sürümündeki "Aşama 2 tekli + Aşama 3 toplu, ayrı tool'lar"
  planından **kökten değişti** — sohbet sırasında kullanıcı, kriter belirleme
  ve tetikleme mantığının dinamik olması gerektiğini, ayrı bir
  `set_dynamic_criteria`/`start_batch_session`/`finalize_batch` tool zincirinin
  gereksiz karmaşıklık olduğunu belirtti. Final tasarım (`ARCHITECTURE.md` §6,
  `AGENTS.md` §1-§3):
  - CV'ler geldiğinde **otomatik** işlenip dosya tabanlı bir bilgi bankasına
    (`data/adaylar/*.md`) yazılır (`submit_cv`, `pre_hook` ile zorunlu çağrı).
  - Değerlendirme **tamamen kullanıcı talebiyle, o anki cümleden** tetiklenir
    (`evaluate_candidates(criteria, scope_hint)`) — kriterler hiçbir yerde
    saklanmaz, her istekte taze gelir. Tekli/toplu ayrımı ayrı tool'lar değil,
    bulunan aday sayısına göre kod içinde dallanıyor.
  - Kod tabanı:
    - `domain/`: `CandidateProfile` (zengin ama düz — nested obje yok),
      `SingleAnalysisResult`, `CriterionScores`/`CandidateScore`/`BatchAnalysisResult`,
      `PdfValidationResult`
    - `services/pdf_validator.py` — 7 birim testiyle doğrulandı (mock'suz,
      gerçek elle üretilmiş PDF fixture'ları), **hepsi geçiyor**
    - `services/candidate_store.py` — markdown yazıcı/okuyucu, `slugify`,
      `resolve_document_path`
    - `agents/`: `extraction_agent`, `analysis_agent`, `scoring_agent`
    - `workflows/cv_processing_workflow.py` — `validate_pdf` → `extract_cv`,
      **LLM'siz uçtan uca test edildi** (geçersiz PDF ile `stop=True` doğru
      tetikleniyor, `extract_cv` hiç çağrılmıyor)
    - `workflows/batch_scoring.py` — `Parallel` + `_RankTop3Executor`
    - `main.py` — `submit_cv`, `evaluate_candidates`, `pre_hook`, tüm wiring.
      **Construction testi geçti** (dummy token/key ile import+kurulum doğrulandı).
  - **ÖNEMLİ, KAPANMAMIŞ RİSK:** `FilesystemContextProvider.aquery()`'nin
    gerçek `Document.uri` formatı **canlı bir LLM çağrısı gerektirdiği için bu
    oturumda test edilemedi**. `evaluate_candidates`'ta `scope_hint` boşken
    (en yaygın senaryo — "bunları karşılaştır") tamamen deterministik bir
    fallback var (`candidate_store.list_all_candidates()`, agentic aramaya
    hiç bağımlı değil) — bu yüzden ÇEKİRDEK senaryo risksiz. Risk sadece
    `scope_hint` dolu olduğunda (belirli isim(ler) söylenince) devreye giriyor.
    **Yeni oturumun ilk işi bu olmalı:** gerçek bir CV yükleyip `scope_hint`'li
    bir sorgu ("Ahmet'i değerlendir" gibi) deneyip `resolve_document_path`'in
    gerçekten dosya bulup bulmadığını gözlemlemek; bulamıyorsa
    `services/candidate_store.py::resolve_document_path`'i gerçek `Document`
    çıktısına göre düzeltmek.
  - `CandidateProfile` ayrıca bu oturumda kullanıcının paylaştığı daha zengin
    bir "NormalizedCV" şemasından seçici olarak genişletildi (`title`, `links`,
    `total_experience_years`, `work_model`, `employment_type`, `notice_period`,
    `military_status`, `certifications`, `languages` eklendi) — bilinçli olarak
    DÜZ tutuldu, nested obje/enum eklenmedi (KISS).

## 2. Kaynaklar

- **GitHub reposu:** https://github.com/Wijt/telegram-ai-hr-bot (private,
  `gh` CLI zaten `Wijt` hesabıyla oturum açmış durumda)
- **Orijinal ödev dokümanı — repo dışında, unutulmasın:**
  `C:\Users\fkaya\OneDrive\Desktop\SisOft\Yapay Zeka Projesi Telegram API Mülakat Ödevi.pdf`
  (repo kökü `SisOft\ilk\` içinde, PDF bir üst klasörde). Tüm mimari kararlar bu
  dokümanın birebir alıntılarıyla gerekçelendirildi (`ARCHITECTURE.md` §10'da
  bir karşılama tablosu var); şüpheye düşülürse doğrudan bu dosyaya bakılmalı.

## 3. Altyapı — repoda yazılı olmayan operasyonel bilgiler

Kullanıcının **kendi self-hosted** Tailscale-uyumlu ağı (Headscale + Headplane) ve
VPS'i var, ngrok yerine bunu kullanıyor. Zaten kurulup **çalışır durumda**:

- VPS public IP: `89.47.113.65`
- Dev makine (botun çalıştığı yer) Headscale IP'si: `100.64.0.2`
- Public domain: `sisoft-agentos.iamfurkan.com` (Cloudflare proxy arkasında,
  otomatik HTTPS — Cloudflare edge sertifikası Telegram için geçerli)
- VPS'te Dokploy ile bir `alpine/socat` container'ı çalışıyor:
  `TCP4-LISTEN:7777,fork,reuseaddr` → `TCP4:100.64.0.2:7777`
  (Zincir: Telegram → Cloudflare → VPS:7777 → socat → Headscale tailnet →
  dev makine:7777 → Agno AgentOS)
- **Telegram webhook zaten kayıtlı**: `https://sisoft-agentos.iamfurkan.com/telegram/webhook`
  — yeniden kaydetmeye gerek yok, sadece bot süreci (`python main.py`) dev
  makinede çalışır durumda olmalı.
- `.env`'de `APP_ENV=development` olduğu sürece webhook secret token
  doğrulaması tamamen atlanıyor (`agno/os/interfaces/telegram/security.py`,
  `_is_dev_mode()`). Bunu değiştirmeden önce `TELEGRAM_WEBHOOK_SECRET_TOKEN`
  set edilmezse **sunucu ilk mesajda hata verir** — dikkat.
- Bu ortamda (Claude Code sandbox) PyPI'a düz `pip install` **SSL hatası
  veriyor** (sandbox proxy'sinin self-signed sertifikası) — `Bash`/`PowerShell`
  çağrılarında `dangerouslyDisableSandbox: true` ile çalışıyor. Bu, dev
  makinenin kendi ortamını etkilemez, sadece bu araç içindeki test kurulumları
  için geçerli bir not.
- **Dokploy MCP'si bu oturumda bağlıydı, sonra bağlantısı koptu** (uzun oturum
  sırasında bir noktada disconnect oldu, sistem mesajıyla bildirildi). Yeni
  oturumda tekrar bağlıysa, VPS tarafında bir şey değiştirmek gerekirse
  kullanılabilir — sormadan aksiyon alınmamalı.

**Botu çalıştırma (dev makinede):**
```powershell
cd src
python main.py
```
`PYTHONPATH` ayarlamaya gerek yok. `.venv` zaten kurulu; yeni bağımlılık
eklenirse `..\.venv\Scripts\python.exe -m pip install -r requirements.txt`
(`pypdf`, `pytest` Aşama 2'de eklendi).

**Testleri çalıştırma:**
```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

## 4. Neden Agno, neden LangChain değil (özet)

- **Hazır Telegram interface'i** — webhook, session/user_id eşleme, medya
  indirme hazır; LangChain'de "Telegram entegrasyonu" sadece bir chat-history
  *loader*, canlı bot sunmuyor.
- **`output_schema`** — ödevin "ortak JSON şeması" gereksinimine birebir uygun.
- **`Workflow` primitifi** (`Step`, `Parallel`, `StepOutput(stop=True)`) — "LLM
  router, kod garantör" ilkemizle (`AGENTS.md` §5) birebir örtüşüyor.
- **Model-agnostic** — OpenAI→Ollama geçişi tek satır.
- LangChain'in artıları (daha büyük ekosistem) bilinçli feda edildi; Agno'nun
  kendi dokümantasyonunu doğrudan araştırarak telafi edildi.

## 5. Bu oturumda düzeltilen/doğrulanan Agno API detayları

Hepsi **kurulu Agno paketinin kaynağına bakılarak** (`.venv/Lib/site-packages/agno/`)
ya da izole, LLM'siz test scriptleriyle doğrulandı — varsayımla değil. Yeni
oturum da aynı disiplini sürdürmeli: emin olunmayan bir davranış varsa önce
`grep`/`cat` ile kaynağa bakılmalı ya da minik bir test scriptiyle denenmeli.

- **`AgentOS.serve()`'in varsayılan `host`'u `"localhost"`** — uzaktan erişim
  için `host="0.0.0.0"` şart.
- **`db`, `Agent`'a değil `AgentOS`'a verilmeli** — `AgentOS(db=SqliteDb(...))`,
  kendi `db`'si olmayan her bileşene otomatik atanıyor.
- **`src/` altında ayrı bir paket adı yok, bilinçli** — Python script'in
  dizinini otomatik `sys.path`'e ekliyor, `pip install -e .` gereksiz.
- **PowerShell'de `$env:VAR="value"`**, `set VAR=value` (cmd.exe) sessizce
  işe yaramaz.
- **`data/` klasörü kalıcı veri için, `tmp/` değil.**
- **Structured output, Workflow adımları arasında tipli Pydantic nesnesi
  olarak akar** (string'e çevrilmez).
- **`files`, tool'lara built-in parametre olarak otomatik enjekte edilir**
  (`files: Optional[Sequence[File]] = None`).
- **`WorkflowRunOutput`'ta `.stopped` diye bir alan YOK.** `stop=True`'yu doğru
  tespit etmenin yolu: `sonuc.step_results[-1].stop` (izole testle doğrulandı
  — `RunStatus` her iki durumda da `completed` kalıyor, ona bakılamaz). Bu,
  kullanıcının kendisi "kodun içine bakabilirsin, str dönerse hata ne demek"
  diyerek yakalattığı gerçek bir bug'dı — `isinstance(content, str)` ile hata
  tespiti yanlıştı.
- **`Parallel` bloğundan sonra `step_input.previous_step_content` SADECE SON
  dalın çıktısını taşır, hepsini değil!** Her dalın sonucuna ayrı ayrı
  `step_input.get_step_content(step_adı)` ile erişilmeli (izole testle
  doğrulandı — bu, fark edilmeseydi ciddi, sessiz bir bug olurdu).
- **`Workflow.run(files=[...])`, ilk adımın `step_input.files`'ına doğru
  şekilde ulaşıyor** (izole testle doğrulandı).
- **`Workflow.arun`/`Agent.arun` mevcut ve `files=`/`input=` kabul ediyor.**
- **`pre_hooks` (çoğul, liste), `pre_hook` (tekil) değil.** Hook fonksiyonu
  `run_input: RunInput` (o turun `.files`'ı burada) ve `agent: Agent` (nesnenin
  kendisi) gibi argümanları isim eşleşmesiyle alabiliyor
  (`agno/utils/hooks.py: filter_hook_args`). `agent.tool_choice`'u doğrudan
  mutate ederek belirli bir tool'u zorlamak mümkün — dict formatı
  (`{"type": "function", "function": {"name": "..."}}`) OpenAI'nin kendi
  API'sine **birebir, değiştirilmeden** aktarılıyor
  (`agno/models/openai/chat.py: request_params["tool_choice"] = tool_choice`).
  Her turda ya zorlanmalı ya da `"auto"`'ya sıfırlanmalı — agent nesnesi
  turlar arası paylaşıldığı için.
- **`FilesystemContextProvider.query()`/`aquery(question: str) -> Answer`**
  bir Agent'a `tools=` olarak bağlamadan **doğrudan çağrılabiliyor**.
  `Answer(results: list[Document], text)`, `Document(id, name, uri, source,
  snippet)`. **Ama bu, canlı LLM çağrısı gerektirdiği için `Document.uri`'nin
  gerçek formatı bu oturumda test edilemedi** — bkz. §1'deki açık risk.
- **`agno.media.File(content=b"", ...)` Pydantic validasyonunda hata verir**
  ("en az biri sağlanmalı" — boş bytes "sağlanmamış" sayılıyor). Gerçek
  Telegram akışında muhtemelen sorun değil (Telegram sıfır byte'lık dosya
  yüklemeyi zaten engelliyor olabilir) ama not düşüldü, doğrulanmadı.

## 6. Araştırma yöntemi / bağlı MCP'ler

- Bu oturumda Agno'ya özel bir docs MCP bağlandı, sonra bağlantısı koptu.
  Yeni oturumda bağlı değilse `WebFetch` ile `docs.agno.com/llms.txt`
  (konu bazlı index) eşdeğer bir fallback.
- **En güvenilir yöntem: kurulu paketin kaynağına doğrudan bakmak**
  (`grep -rn "..." .venv/Lib/site-packages/agno/`) — dokümantasyon eksik
  kaldığında (örn. `pre_hooks` argüman listesi, `stop=True` tespiti,
  `Parallel` çıktı şekli) bu, dokümandan çok daha güvenilir sonuç verdi.
- **İkinci en güvenilir yöntem: izole, LLM'siz test scriptleri** —
  `Step`/`Workflow`/`StepOutput` gibi yapıların gerçek çalışma zamanı
  davranışını (`.stop`, `get_step_content`, `files` akışı) doğrulamak için
  gerçek bir OpenAI çağrısı gerekmiyor, dummy `executor` fonksiyonlarıyla
  saniyeler içinde test edilebiliyor. **Bu proje boyunca defalarca gerçek bir
  hatayı implementasyondan ÖNCE yakaladı** — yeni oturum da LLM gerektirmeyen
  her mekanizmayı yazmadan önce böyle test etmeli.

## 7. Sıradaki adım — canlı test (Aşama 2 doğrulaması)

Kod tamamlandı, sıradaki iş **kullanıcının kendi OpenAI key'iyle canlı test**:

1. Botu başlat (`cd src && python main.py`), Telegram'da gerçek bir CV PDF'i
   gönder → "bilgi bankasına eklendi" mesajı beklenir → `src/data/adaylar/*.md`
   dosyasının oluştuğu (ve içeriğinin makul olduğu) kontrol edilmeli.
2. "Bu adayı [kriter]'e göre değerlendir" de → Markdown rapor beklenir.
3. 2-3 CV daha gönder, "Bunları karşılaştır [kriter]" de → JSON top-3 çıktısı
   beklenir (ödev şemasıyla birebir: `status`, `processedCVCount`,
   `userDefinedCriteria`, `topCandidates[]`).
4. Bozuk/şifreli/sahte-uzantılı bir dosya gönder → net Türkçe hata mesajı,
   hiçbir OpenAI çağrısı yapılmadan (log'da `extract_cv` adımının hiç
   çalışmadığı görülebilir).
5. `scope_hint` gerektiren bir senaryo dene ("sadece Ahmet'i değerlendir") —
   §1'deki açık riski bununla kapat.

Hata çıkarsa önce §5'teki doğrulanmış API detaylarına, sonra gerekirse tekrar
kurulu paketin kaynağına bakılmalı — tahmin yürütülmemeli.

## 8. Sonraki iterasyon (v1 sonrası, ödevin çekirdeğine dahil değil)

`ARCHITECTURE.md` §11'de listelenen: Docker/docker-compose, `MODEL_PROVIDER=ollama`
ile canlı test, OCR destekli taranmış PDF okuma, çoklu kullanıcı yük testleri,
mesaj bazlı rate limiting.

## 9. Ödevin 4 değerlendirme kriteri — unutulmasın

1. **Dinamik Prompt Başarısı** — kriterleri prompt'a gömme, tekli+toplu modları
   kararlı çalıştırma (artık ikisi de tek bir `evaluate_candidates` tool'u,
   "kaç aday bulundu" sayımına göre dallanıyor — ayrı komutlara gerek yok)
2. **PDF Doğrulama & LLM Extraction Kalitesi** — bozuk yapıları yakalama,
   dağınık metni ortak JSON'a hatasız çıkarma
3. **Asenkron Süreç ve Bağlam Yönetimi** — thread'lerin kilitlenmemesi, çoklu
   dosyada bot yanıt vermeye devam etmesi, chat geçmişinin korunması
4. **Vibe Coding Hakimiyeti** — AI ile üretilen kodun mimarisine/dil
   pratiklerine/istisna yönetimine tam hakim olma (mülakatta her satır
   savunulabilir olmalı — bu yüzden `ARCHITECTURE.md`/`AGENTS.md` bu kadar
   ayrıntılı, ve bu oturumdaki her önemli API varsayımı kod okunarak/test
   edilerek doğrulandı, kabul edilmedi)
