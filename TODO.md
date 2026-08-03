# Devir Notu / TODO — telegram-ai-hr-bot

Bu dosya, farklı bir Claude Code oturumuna geçilirken bağlamın kaybolmaması için
yazıldı. **Yeni oturum kod yazmaya başlamadan önce sırasıyla şunları okumalı:**

1. Bu dosya (özet + operasyonel bilgi + somut sıradaki adımlar)
2. `AGENTS.md` §0 — çalışma ilkeleri (KISS, aşamalı geliştirme, best-practice
   zorunluluğu). **Bunlara uyulmadan yazılan kod muhtemelen geri alınacaktır.**
3. `ARCHITECTURE.md` — tüm mimari kararlar ve *neden* öyle karar verildiği
4. `AGENTS.md` §1'den itibaren — ajan/tool/pipeline'ların kod karşılığı

Aşağıdakiler bu üç dosyada **olmayan**, sadece bu oturumda öğrenilen/kurulan
bilgiler.

## 1. Şu anki durum (son commit: `da942e0`)

- **Aşama 0 — Hello World: ✅ tamamlandı ve gerçek Telegram botuyla doğrulandı.**
- **Aşama 1 — Sohbet + session (SqliteDb): ✅ tamamlandı**, henüz kullanıcı
  tarafından "adımı hatırlıyor mu" testi teyit edilmedi (son mesajımda test
  istendi, cevap bekleniyor).
- Aşama 2 (dinamik kriter + tekli CV) ve sonrası **henüz kod olarak yazılmadı** —
  sadece `ARCHITECTURE.md`/`AGENTS.md`'de tasarlandı.

## 2. Altyapı — repoda yazılı olmayan operasyonel bilgiler

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

**Botu çalıştırma (dev makinede):**
```powershell
cd src
python main.py
```
`PYTHONPATH` ayarlamaya gerek yok (bkz. §3). `.venv` zaten kurulu; yeni bir
bağımlılık eklenirse `..\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

## 3. Bu oturumda düzeltilen yanlış varsayımlar (tekrar keşfedilmesin diye)

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

## 4. Sıradaki adımlar — Aşama 2 (dinamik kriter + tekli CV analizi)

`ARCHITECTURE.md` §6, §9, `AGENTS.md` §2, §4, §5'in doğrudan kod karşılığı.

- [ ] `requirements.txt`'e `pypdf` ekle
- [ ] `domain/`: `CandidateProfile`, `SingleAnalysisResult`, `PdfValidationResult`
      (Pydantic modelleri, `ARCHITECTURE.md` §7'deki alan adlarıyla birebir)
- [ ] `services/pdf_validator.py`: `PdfValidator.validate()` — 6 kontrol sırayla
      (`ARCHITECTURE.md` §9 tablosu). **LLM içermez.**
- [ ] `tests/test_pdf_validator.py`: gerçek, elle hazırlanmış bozuk/şifreli/boş/
      sahte-uzantılı örnek dosyalarla — mock yok (dış çağrı olmadığı için gerek yok)
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

## 5. Ondan sonrası — Aşama 3 (toplu CV + paralel skorlama)

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

## 6. Opsiyonel (v1 sonrası, ödevin çekirdeğine dahil değil)

- Aşama 4: `data/adaylar/<aday>/` klasör yapısı + `FilesystemContextProvider`
  ile Router'ın geçmiş adaylar hakkında soru cevaplayabilmesi
- Aşama 5: `MODEL_PROVIDER=ollama` ile canlı test, Dockerfile/docker-compose

## 7. Yeni oturuma tavsiye

Kod yazmadan önce Agno'nun resmi dokümantasyonunu/örneklerini araştırmaya devam
edin — bu oturumda defalarca, varsayımla ilerlemek yerine ya kurulu paketin
kaynağına (`.venv/Lib/site-packages/agno/`) bakmanın ya da resmi dokümanları
aramanın yanlış varsayımları düzelttiği görüldü (host="0.0.0.0" gerekliliği,
db'nin AgentOS seviyesinde olması, src-layout'un gereksizliği, vb.). Emin
olmadığınız bir Agno API detayı varsa, tahmin etmek yerine önce doğrulayın.
