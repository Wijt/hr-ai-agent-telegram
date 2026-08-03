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

## 1. Şu anki durum (son commit: `da942e0`)

- **Aşama 0 — Hello World: ✅ tamamlandı ve gerçek Telegram botuyla doğrulandı.**
- **Aşama 1 — Sohbet + session (SqliteDb): ✅ tamamlandı**, henüz kullanıcı
  tarafından "adımı hatırlıyor mu" testi teyit edilmedi (son mesajımda test
  istendi, cevap bekleniyor).
- Aşama 2 (dinamik kriter + tekli CV) ve sonrası **henüz kod olarak yazılmadı** —
  sadece `ARCHITECTURE.md`/`AGENTS.md`'de tasarlandı.

## 2. Kaynaklar

- **GitHub reposu:** https://github.com/Wijt/telegram-ai-hr-bot (private,
  `gh` CLI zaten `Wijt` hesabıyla oturum açmış durumda)
- **Orijinal ödev dokümanı — repo dışında, unutulmasın:**
  `C:\Users\fkaya\OneDrive\Desktop\SisOft\Yapay Zeka Projesi Telegram API Mülakat Ödevi.pdf`
  (repo kökü `SisOft\ilk\` içinde, PDF bir üst klasörde). Tüm mimari kararlar bu
  dokümanın birebir alıntılarıyla gerekçelendirildi (`ARCHITECTURE.md` içinde
  §-referanslı alıntılar var); şüpheye düşülürse doğrudan bu dosyaya bakılmalı.

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
- **Dokploy MCP'si bu oturumda bağlıydı** (`mcp__dokploy-mcp__*` araçları) —
  kullanıcının VPS'indeki Dokploy'u doğrudan yönetebilecek araçlar mevcuttu
  (application/compose create-deploy-logs vb.), kullanılmadı çünkü kullanıcı
  socat container'ını kendisi kurdu. Yeni oturumda bu MCP bağlıysa (araç
  listesinde `dokploy-mcp` görünüyorsa), Aşama 5'teki Docker deploy'unda ya da
  VPS tarafında bir şey değiştirmek gerekirse kullanıcı adına doğrudan
  kullanılabilir — sormadan aksiyon alınmamalı, sadece imkan olarak not düşüldü.

**Botu çalıştırma (dev makinede):**
```powershell
cd src
python main.py
```
`PYTHONPATH` ayarlamaya gerek yok (bkz. §5). `.venv` zaten kurulu; yeni bir
bağımlılık eklenirse `..\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

## 4. Neden Agno, neden LangChain değil (özet — detay sadece sohbet geçmişinde vardı)

Proje başında LangChain vs Agno karşılaştırması yapıldı, Agno seçildi. Gerekçe
özetle:
- **Hazır Telegram interface'i** (`agno.os.interfaces.telegram.Telegram`) —
  webhook, session/user_id eşleme, medya indirme hazır; LangChain'de "Telegram
  entegrasyonu" sadece bir chat-history *loader* (RAG için), canlı bot sunmuyor.
- **`output_schema` ile yapılandırılmış çıktı** — ödevin "LLM Extraction → ortak
  JSON şeması" gereksinimi için birebir uygun, LangChain'in `with_structured_output`'una
  denk ama framework'ün geri kalanıyla (Workflow, Telegram interface) daha
  bütünleşik.
- **`Workflow` primitifi** — ardışık/paralel çok adımlı ajan zincirleri için
  resmi, adı konmuş bir desen (`Step`, `Parallel`, `StepOutput(stop=True)`) —
  bizim "LLM router, kod garantör" ilkemizle (`AGENTS.md` §5) birebir örtüşüyor.
- **Model-agnostic** — OpenAI'dan Ollama'ya geçiş tek satır (`agno.models.ollama.Ollama`),
  ödevin "yerel veya uzak LLM" gereksinimini karşılıyor.
- Karşı taraf (LangChain'in artıları: daha büyük ekosistem/dokümantasyon hacmi,
  AI kod asistanlarının onu daha "iyi bildiği") bilinçli olarak Agno lehine
  feda edildi — gerekçe: Agno'nun kendi resmi MCP'si/dokümantasyonu üzerinden
  doğrudan araştırma yaparak bu dezavantajı bir ölçüde telafi ettik (bkz. §6).

## 5. Bu oturumda düzeltilen yanlış varsayımlar (tekrar keşfedilmesin diye)

Bunların hepsi **kurulu Agno paketinin kaynağına bakılarak** ya da resmi
dokümantasyon araştırılarak doğrulandı, varsayımla değil — yeni oturum da aynı
disiplini sürdürmeli (`.venv/Lib/site-packages/agno/` yerelde mevcut, doğrudan
okunabilir).

- **`AgentOS.serve()`'in varsayılan `host`'u `"localhost"`** — uzaktan (Tailscale
  relay dahil) erişim için `host="0.0.0.0"` şart. `main.py`'de zaten ayarlı,
  ama yeni bir çalıştırma noktası eklenirse unutulmasın.
- **`db`, `Agent`'a değil `AgentOS`'a verilmeli.** `AgentOS(db=SqliteDb(...))`,
  kendi `db`'si olmayan her agent/team/workflow'a otomatik atanıyor
  (`agno/os/app.py`: `if self.db is not None and agent.db is None: agent.db = self.db`).
  Aşama 2-3'te eklenecek `cv_processing_workflow`, `extraction_agent` vb. hiçbir
  şey yapmadan aynı db dosyasını (`data/agent-os.db`) paylaşacak.
- **`src/` altında ayrı bir paket adı (`hrbot/`) yok, bilinçli olarak.**
  src-layout + `pip install -e .` bir kütüphane dağıtacaksak mantıklı, tek bir
  bot deploy ederken gereksiz katman — kaldırıldı. Python zaten çalıştırılan
  script'in dizinini `sys.path`'e otomatik ekliyor.
- **PowerShell'de ortam değişkeni `$env:VAR="value"` ile ayarlanır**, `set
  VAR=value` (cmd.exe sözdizimi) PowerShell'de sessizce işe yaramaz.
- **`data/` klasörü kalıcı veri için, `tmp/` değil** — session/history ve
  (Aşama 4'te) aday dosyaları atılabilir değil. İkisi de `.gitignore`'da.
- **Structured output, Workflow adımları arasında string'e çevrilmeden, tipli
  Pydantic nesnesi olarak akar** — `extract_cv` adımının `output_schema=CandidateProfile`
  çıktısı, bir sonraki adımın `step_input.previous_step_content`'inde doğrudan
  `CandidateProfile` örneği olarak gelir (resmi `structured-io-at-each-step-level`
  örneğiyle doğrulandı).
- **Tool'lara medya (`files`), `files: Optional[Sequence[File]] = None` gibi bir
  built-in parametre ile otomatik enjekte edilir** — LLM'in dosya içeriğini
  argüman olarak "yazdırmasına" gerek yok (`agno/tools/overview` — built-in
  tool parametreleri: `run_context`, `agent`, `team`, `images`/`videos`/`audios`/`files`).

## 6. Bu oturumda kullanılan araştırma yöntemi / bağlı MCP'ler

- **Agno'ya özel bir docs MCP** oturum ortasında kullanıcı tarafından bağlandı
  (`mcp__<id>__search_agno`, `mcp__<id>__query_docs_filesystem_agno`). Yeni
  oturumda bu bağlı değilse, aynı içeriğe `WebFetch` ile `docs.agno.com` (özellikle
  `docs.agno.com/llms.txt` — tüm sayfaların konu bazlı index'i) üzerinden
  ulaşmak bu oturumda da defalarca işe yaradı, eşdeğer bir fallback.
- **LangChain'e özel bir docs MCP de bağlıydı** (proje başındaki karşılaştırma
  için kullanıldı, `docs.langchain.com` içeriği).
- **En güvenilir doğrulama yöntemi:** kurulu paketin kaynağına doğrudan bakmak
  (`grep`/`cat` ile `.venv/Lib/site-packages/agno/...`) — dokümantasyon bazen
  eksik/belirsiz kaldığında (örn. secret token doğrulama mantığı, `AgentOS`
  constructor'ının tam parametre listesi) bu, varsayımdan çok daha güvenilir
  sonuç verdi. Emin olunmayan bir Agno davranışı varsa önce buna bakılmalı.
- **`visualize` (diyagram) aracı** mimari diyagramı çizmek için kullanıldı,
  README.md'deki Mermaid diyagramı onun GitHub'da render olan eşdeğeri.

## 7. Sıradaki adımlar — Aşama 2 (dinamik kriter + tekli CV analizi)

`ARCHITECTURE.md` §6, §9, `AGENTS.md` §2, §4, §5'in doğrudan kod karşılığı.

- [ ] `requirements.txt`'e `pypdf` ekle
- [ ] `domain/`: `CandidateProfile`, `SingleAnalysisResult`, `PdfValidationResult`
      (Pydantic modelleri, `ARCHITECTURE.md` §7'deki alan adlarıyla birebir)
- [ ] `services/pdf_validator.py`: `PdfValidator.validate()` — 6 kontrol sırayla
      (`ARCHITECTURE.md` §9 tablosu). **LLM içermez.**
- [ ] `tests/test_pdf_validator.py`: gerçek, elle hazırlanmış bozuk/şifreli/boş/
      sahte-uzantılı örnek dosyalarla — mock yok (dış çağrı olmadığı için gerek
      yok). **Bu fixture dosyalar henüz yok, testle birlikte üretilmeli** (örn.
      `pypdf` ile şifreli bir PDF oluşturmak, geçerli bir PDF'in son N baytını
      kesip bozuk hâle getirmek, 0 baytlık dosya, `.txt` içeriğini `.pdf` diye
      kaydetmek).
- [ ] `agents/extraction_agent.py`: `output_schema=CandidateProfile`
- [ ] `agents/analysis_agent.py`: `output_schema=SingleAnalysisResult`
- [ ] `workflows/cv_processing_workflow.py`: `validate_pdf` (function,
      `StepOutput(stop=True)` kapısı) → `extract_cv` (Agent step) — **tek,
      paylaşılan tarif**, Aşama 3'te de değişmeden reuse edilecek
- [ ] `workflows/single_cv_workflow.py`: `cv_processing_workflow`'u iç adım
      olarak sarar (`Step(workflow=cv_processing_workflow)`) + `analyze_cv`
      (function-executor, kriter + profili birleştirip `analysis_agent`'ı çağırır)
- [ ] `session/`: `session_state` şeması (`mode`, `dynamic_criteria`,
      `batch_files`) + guard yardımcıları
- [ ] `agents/chat_agent.py`: Router Agent'a tool'lar eklenir —
      `set_dynamic_criteria`, `submit_cv` (şimdilik sadece idle dalı: kriter
      varsa `single_cv_workflow`'u hemen çalıştırır). **`pre_hook` ile** o turda
      dosya varsa `tool_choice="submit_cv"` zorunlu kılınmalı (`ARCHITECTURE.md`
      §5) — bu, LLM'in dosya geldiğinde tool çağırmayı "unutmasını" imkansız
      kılan kritik bir güvence, atlanmamalı.
      `send_media_to_model=False, store_media=True` ayarları da bu adımda gelir.

**Başarı kriteri:** Gerçek bir CV PDF'i gönder, kriter söyle (örn. "React
tecrübesi ve temiz koda göre skorla"), Markdown rapor gelsin. Bozuk/şifreli/
sahte-uzantılı bir PDF gönderildiğinde net, anlaşılır bir hata mesajı gelsin —
hiçbir OpenAI çağrısı yapılmadan.

## 8. Ondan sonrası — Aşama 3 (toplu CV + paralel skorlama)

- [ ] `agents/scoring_agent.py`: `output_schema` ile `dynamicScores: dict[str,int]`
      (`Field(ge=0, le=100)`), `hrEvaluation: str`
- [ ] `domain/`: `CandidateScore`, `BatchAnalysisResult` — ödev dokümanındaki
      JSON şemasına **birebir** (camelCase alan adları)
- [ ] `workflows/batch_processing.py`: `ProcessAndScoreExecutor` (class-based,
      her paralel dal kendi dosyasını + kriterleri constructor'da taşır,
      `__call__` içinde **aynı** `cv_processing_workflow.arun(files=[self.file])`
      + `scoring_agent.arun(...)` çağrılır), `rank_top3_fn` (ortalama +
      sıralama, **LLM'siz, deterministik**)
- [ ] Router Agent'a `start_batch_session`, `finalize_batch` tool'ları +
      `submit_cv`'nin batch dalı (bu moddayken dosyayı **işlemeden** biriktirir)

**Başarı kriteri:** 2-5 CV gönder, `/done` yaz, ödev dokümanındaki JSON
formatında top-3 sonucu gelsin.

## 9. Opsiyonel (v1 sonrası, ödevin çekirdeğine dahil değil)

### Aşama 4 — Aday bilgi bankası

Bu, sohbet sırasında derinlemesine araştırıldı, kararı özetliyorum ki yeni
oturum sıfırdan araştırmasın:

- Agno'da bu iş için **iki ayrı, birbiriyle ilgisiz alt sistem** var:
  - `agno.knowledge.Knowledge` — vektör veritabanı (ChromaDB/LanceDB, embedding
    gerektirir), metadata filtreleme, `enable_agentic_knowledge_filters=True`
    ile agent'ın "Furkan Kaya'yı sor" gibi bir soruyu otomatik `filters={"candidate_name":"Furkan Kaya"}`'ya
    çevirmesi. Resmi bir örnek **birebir CV senaryosunu** (5 CV, `user_id` metadata'sıyla) gösteriyor.
  - `agno.context.fs.FilesystemContextProvider` — **vektör DB'siz**, gerçek bir
    dizin ağacını (`root=...`) sarıp agent'a tek bir `query_<id>` tool'u
    veriyor; arka planda salt-okunur bir alt-agent dizini gezip dosya okuyor.
    Hiç embedding/vektör DB gerekmiyor.
- **Karar: Aşama 4'te `FilesystemContextProvider` kullanılacak, vektör DB
  (ChromaDB dahil) değil.** Gerekçe: kullanıcının orijinal isteği zaten gerçek
  "klasör" (`data/adaylar/<aday>/raw_cv.pdf`, `extracted_profile.json`) —
  bu, buna birebir karşılık geliyor; ödev ölçeğinde (birkaç test adayı) vektör
  aramaya gerek yok; sıfır ekstra bağımlılık (chromadb/lancedb/embedder yok).
  Vektör DB (ChromaDB, dosya tabanlı/embedded, sunucu gerekmez) ölçek büyürse
  belgelenmiş bir yükseltme yolu olarak not edildi, bugün kurulmayacak.
- Yazma tarafı: `cv_processing_workflow`'a 3. bir adım (`store_to_knowledge`,
  düz Python fonksiyonu — dosyaları `data/adaylar/...`'a yazar) eklenecek.
- Okuma tarafı: Router Agent'ın `tools=[...]` listesine
  `FilesystemContextProvider(root="data/adaylar", model=get_model()).get_tools()`
  eklenecek.

### Aşama 5

`MODEL_PROVIDER=ollama` ile canlı test, Dockerfile/docker-compose (VPS'te
zaten Dokploy var, MCP'si bağlıysa deploy için kullanılabilir — bkz. §3).

## 10. Ödevin 4 değerlendirme kriteri — unutulmasın

Ödev dokümanının kendi "Değerlendirme Kriterleri" bölümü (yeni oturum orijinal
PDF'i okumazsa bunu unutabilir):

1. **Dinamik Prompt Başarısı** — kriterleri prompt'a gömme, tekli+toplu modları
   kararlı çalıştırma
2. **PDF Doğrulama & LLM Extraction Kalitesi** — bozuk yapıları yakalama,
   dağınık metni ortak JSON'a hatasız çıkarma
3. **Asenkron Süreç ve Bağlam Yönetimi** — thread'lerin kilitlenmemesi, çoklu
   dosyada bot yanıt vermeye devam etmesi, chat geçmişinin korunması
4. **Vibe Coding Hakimiyeti** — AI ile üretilen kodun mimarisine/dil
   pratiklerine/istisna yönetimine tam hakim olma (mülakatta her satır
   savunulabilir olmalı)

Her yeni özellik eklenirken bu dördü akılda tutulmalı — özellikle #4: kod
"çalışıyor" olması yetmez, *neden* böyle yazıldığı açıklanabilir olmalı
(bu yüzden `ARCHITECTURE.md`/`AGENTS.md`'deki gerekçeler bu kadar ayrıntılı).

## 11. Yeni oturuma tavsiye

Kod yazmadan önce Agno'nun resmi dokümantasyonunu/örneklerini araştırmaya devam
edin — bu oturumda defalarca, varsayımla ilerlemek yerine ya kurulu paketin
kaynağına (`.venv/Lib/site-packages/agno/`) bakmanın ya da resmi dokümanları
aramanın yanlış varsayımları düzelttiği görüldü (§5, §6). Emin olmadığınız bir
Agno API detayı varsa, tahmin etmek yerine önce doğrulayın.
