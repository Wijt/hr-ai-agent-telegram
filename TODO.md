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

- **Aşama 0 — Hello World: ✅** gerçek Telegram botuyla doğrulandı.
- **Aşama 1 — Sohbet + session (SqliteDb): ✅** ("adımı hatırlıyor mu" testi
  kullanıcı tarafından hâlâ teyit edilmedi).
- **Aşama 2 — Dinamik kriter + tekli CV: ✅ kod tamam**, birim testler geçiyor
  (7/7), doğrulama kapısı gerçek workflow koşusuyla test edildi (bozuk dosya →
  LLM'e gitmeden hata mesajı). **Kullanıcının gerçek Telegram + gerçek CV testi
  bekleniyor** (başarı kriteri: kriter yaz → PDF gönder → Markdown rapor).
- Aşama 3 (toplu CV + paralel skorlama) henüz yazılmadı.

## 1a. ⚠️ KULLANICI KOD STİLİ TALİMATI — önce bunu oku

Kullanıcı bu oturumda kod stiline sert müdahale etti, sonraki oturumlar aynı hatayı
tekrarlamasın: **radikal KISS istiyor.** Tek fonksiyonluk class yazma (PdfValidator
class'ı silindi → `validate_pdf()` fonksiyonu), sonuç nesnesi/enum kurma (dönüş düz
`(metin, hata)` tuple), `__init__.py`/paket iç içeliği yok (`domain/`, `services/`,
`models/` klasörleri silindi → `src/` altında düz modüller), `conftest.py` yerine
`pytest.ini`, test dosyaları minimal (senaryo başına 1 kısa test). Hata akışı: tool
düz string döndürür, kullanıcıya iletmek agent'ın/framework'ün işi — ekstra makine
kurma. Aşama 3'te de geçerli: `ProcessAndScoreExecutor` **class'ı yerine**
`make_process_and_score(file, criteria)` closure fabrikası (AGENTS.md §4 güncellendi).

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

## 7. Aşama 2 — ✅ TAMAMLANDI (bu oturumda)

Uygulanan yapı (KISS revizyonlu, bkz. §1a): `src/schemas.py` (CandidateProfile,
SingleAnalysisResult), `src/pdf_validator.py` (`validate_pdf() → (metin, hata)`),
`src/agents.py` (extraction + analysis), `src/workflows.py` (cv_processing_workflow
+ `stopped_early()`), `src/bot.py` (Router: `set_dynamic_criteria`, `submit_cv`,
`force_submit_cv_on_file` pre_hook'u), `main.py` (AgentOS'a workflow da kayıtlı).
`tests/test_pdf_validator.py` 7/7 geçiyor.

**Tasarım değişiklikleri (orijinal plana göre — hepsi dokümanlara işlendi):**
- `single_cv_workflow` YOK: `submit_cv` doğrudan `cv_processing_workflow.run()` +
  `analysis_agent.run()` çağırıyor — Aşama 3'ün batch deseniyle birebir aynı şekil.
- `session/` modülü YOK: state `run_context.session_state`'te, başlangıç değeri
  `Agent(session_state={"dynamic_criteria": None})`.
- `submit_cv`'ye `criteria` parametresi eklendi: kullanıcı dosya + kriteri AYNI
  mesajda gönderirse (tool_choice zorlanmışken set_dynamic_criteria çağrılamaz)
  kriter kaybolmasın.
- Agno 2.8.6 gerçekleri: `pre_hooks` (liste; `pre_hook` yok), `tool_choice`
  mutasyonu Agent'ta kalıcı (her turda set/reset), erken durma tespiti
  `step_results[-1].stop` (ayrı alan yok), `submit_cv` `stop_after_tool_call=True`
  (sonsuz zorlama döngüsü koruması + rapor kullanıcıya birebir gider), sync tool
  → Agno `asyncio.to_thread`'e atar (event loop bloklanmaz).

**Kullanıcının canlı testi bekleniyor:** kriter yaz → CV PDF'i gönder → Markdown
rapor; bozuk/şifreli/sahte-uzantılı dosyada LLM'siz net hata mesajı.

## 7a. Sıradaki adımlar — Aşama 3 (toplu CV + paralel skorlama)

Mevcut düz dosyalara eklenir, yeni klasör/class AÇILMAZ (bkz. §1a):

- [ ] `schemas.py`'ye: `CandidateScore`, `BatchAnalysisResult` — ödev dokümanındaki
      JSON şemasına **birebir** (camelCase alan adları, `dynamicScores`
      `Field(ge=0, le=100)`)
- [ ] `agents.py`'ye: `scoring_agent` (`output_schema` ile `dynamicScores` +
      `hrEvaluation`)
- [ ] `workflows.py`'ye: `make_process_and_score(file, criteria)` closure fabrikası
      (class DEĞİL — içinde **aynı** `cv_processing_workflow.arun(files=[file])` +
      `scoring_agent.arun(...)`), `rank_top3` (ortalama + sıralama, **LLM'siz**)
- [ ] `bot.py`'ye: `start_batch_session`, `finalize_batch` tool'ları +
      `submit_cv`'nin batch dalı (bu moddayken dosyayı **işlemeden** biriktirir) +
      `session_state`'e `mode`/`batch_files` anahtarları
- [ ] Dikkat: `finalize_batch` sync tool olarak yazılacaksa içindeki paralel dallar
      async (`arun`) — sync tool zaten thread'e atıldığı için içeride
      `asyncio.run(batch_workflow.arun(...))` gerekebilir; yazmadan önce Agno'nun
      `Parallel`'ının sync `run()` yolunda da dalları eşzamanlı koşturup
      koşturmadığını kurulu kaynaktan doğrula (bilinmiyor, varsayma!)

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
