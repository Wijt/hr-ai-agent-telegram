# Ajan Tasarımı — telegram-ai-hr-bot

`ARCHITECTURE.md`'de tanımlanan sistemin ajan/tool envanteri. Bu dosya, her ajanın
*neden var olduğunu*, *ne zaman çağrıldığını* ve *hangi şemayla konuştuğunu* kayıt
altına alır — implementasyon sırasında `src/hrbot/agents/` altındaki kodun doğrudan
karşılığıdır.

## Tasarım İlkesi

Tek bir "her şeyi yapan" ajan yerine, **bir router + üç uzman ajan** modeli:

- **Router Agent** — Telegram'a bağlı tek ajan. Kullanıcıyla doğrudan konuşan bu.
  Kendi başına CV analiz etmez; ne zaman hangi uzman ajanın/servisin devreye
  gireceğine tool-calling ile karar verir.
- **Extraction / Analysis / Scoring** ajanları LLM tarafından *seçilmez* — Router'ın
  tool'ları içinden Python kodu tarafından *çağrılır*. Bu ayrım kararlılık için
  kritik (bkz. `ARCHITECTURE.md` §5).

---

## 1. Router Agent

**Dosya:** `agents/chat_agent.py`
**Bağlı olduğu arayüz:** Agno `Telegram` interface (`AgentOS(interfaces=[Telegram(agent=router_agent)])`)
**Model:** `model_factory.get_model()` (varsayılan OpenAI, env ile Ollama'ya geçer)
**db:** `SqliteDb` — session/history + `session_state` kalıcılığı

**Instructions (özet, Türkçe):**
- Varsayılan davranış: samimi, kısa, bağlamı koruyan bir sohbet asistanı gibi yanıt ver.
- Kullanıcı puanlama/kriter tanımlıyorsa (`"...göre skorla"`, `"...kriterlerine göre
  değerlendir"` gibi ifadeler) → `set_dynamic_criteria` tool'unu çağır.
- Kullanıcı `/batch_analyze` yazdıysa veya birden fazla CV göndereceğini belirtiyorsa
  → `start_batch_session` çağır.
- Kullanıcı bir PDF belgesi gönderdiyse → **her zaman** `submit_cv` çağır (karar
  verme, tool zaten mevcut duruma göre doğru şeyi yapacak).
- Kullanıcı `/done` yazdıysa → `finalize_batch` çağır.
- Asla CV içeriğini kendi başına yorumlama/skorlama — bu iş tool'ların içindeki
  uzman ajanlara ait.

**Tool envanteri:**

| Tool | İmza | Ne yapar |
|---|---|---|
| `set_dynamic_criteria` | `(run_context, criteria: list[str]) -> str` | Kullanıcının serbest metnini LLM zaten tool-call argümanı olarak listeye çevirir; `session_state["dynamic_criteria"]` güncellenir. |
| `start_batch_session` | `(run_context) -> str` | `session_state["mode"] = "collecting_batch"`, `batch_cvs = []`. Kriter tanımlı değilse kullanıcıyı önce kritere yönlendirir. |
| `submit_cv` | `(run_context) -> str` | Bkz. §2. Mod'a göre tekli ya da batch'e ekleme davranışı. |
| `finalize_batch` | `(run_context) -> str` | Bkz. §4. Toplanan CV'leri skorlar, JSON döner, mode'u `idle`'a çeker. |

**Kullanılmayan/gerek olmayan tool'lar:** `reset` — Agno'nun native `/new` komutu
session_state'i zaten sıfırlıyor, tekrar yazılmayacak.

---

## 2. `submit_cv` — Deterministik Yönlendirme Mantığı

Bu, Router'ın en kritik tool'u; LLM sadece *"bir CV geldi, bunu çağır"* kararını
verir, gerisi tamamen Python:

```
submit_cv(run_context):
    dosya = run_context'ten o turun ekli dosyası  # ⚠ bkz. ARCHITECTURE.md §9 (spike gerekli)
    if dosya yok:
        return "Bir PDF dosyası göndermelisin."

    validasyon = PdfValidator.validate(dosya)      # services/pdf_validator.py
    if validasyon başarısız:
        return validasyon.hata_mesajı              # bozuk/şifreli/okunamaz PDF

    metin = extract_text(dosya)                    # services/pdf_text_extractor.py
    profile = ExtractionAgent.run(metin)            # -> CandidateProfile (output_schema)

    if session_state["mode"] == "collecting_batch":
        if session_state["dynamic_criteria"] boş:
            return "Önce kriterleri tanımlamalısın."
        session_state["batch_cvs"].append((profile, dosya.filename))
        if len(batch_cvs) == 5:
            return finalize_batch(run_context)      # otomatik tetikleme
        return f"{len(batch_cvs)}/5 CV alındı. Daha fazla gönder ya da /done yaz."

    else:  # idle -> tekli analiz
        if session_state["dynamic_criteria"] boş:
            return "Bu CV'yi hangi kriterlere göre değerlendirmemi istersin?"
        sonuc = AnalysisAgent.run(profile, session_state["dynamic_criteria"])
        return sonuc.markdown_report
```

---

## 3. Extraction Agent

**Dosya:** `agents/extraction_agent.py`
**Rolü:** LLM Extraction — ham, dağınık CV metnini ortak `CandidateProfile` JSON
şemasına normalize eder (ödevin "farklı formatları standartlaştırma" gereksinimi).
**`output_schema`:** `CandidateProfile` (`full_name`, `skills`, `work_experience`,
`languages`, `education`)
**Instructions (özet):** *"Sana verilen ham CV metninden yalnızca açıkça belirtilmiş
bilgileri çıkar. Emin olmadığın alanları boş bırak, uydurma."*
**Çağrılma şekli:** Router'ın `submit_cv` tool'u içinden düz fonksiyon çağrısı —
LLM tarafından seçilmez.

## 4. Analysis Agent (tekli CV)

**Dosya:** `agents/analysis_agent.py`
**Rolü:** Tek bir `CandidateProfile` + kullanıcının dinamik kriterlerini alıp nitel
bir İK raporu üretir.
**`output_schema`:** `SingleAnalysisResult` (`candidate_name`, `strengths`,
`weaknesses`, `recommendations`, `markdown_report`)
**Instructions (özet):** *"Bir İK uzmanı gibi davran. Sadece verilen kriterlere göre
değerlendir, kriter dışı özellikleri yorumlama. Güçlü/zayıf yönleri ve somut gelişim
tavsiyelerini Türkçe, okunaklı bir Markdown raporu olarak üret."*
**Çağrılma şekli:** `submit_cv` içinden, sadece `mode == idle` ve kriter tanımlıysa.

## 5. Scoring Agent (çoklu CV)

**Dosya:** `agents/scoring_agent.py`
**Rolü:** Bir `CandidateProfile` + dinamik kriter listesini alıp **her kritere ayrı
ayrı 0-100 arası puan** verir (ödevin `dynamicScores` alanı).
**`output_schema`:** `CandidateScore` alt kümesi — `dynamicScores: dict[str, int]`,
`hrEvaluation: str` (kısa gerekçe).
**Çağrılma şekli:** `finalize_batch` içinden, toplanan her CV için **paralel**
(`asyncio.gather` + `Semaphore(MAX_CONCURRENT_CV)`) — bkz. `ARCHITECTURE.md` §7.
**Sıralama:** `averageScore` Python'da hesaplanır (LLM'e bırakılmaz — aritmetik
ortalama deterministik olmalı), ilk 3 aday `rank` ile döner.

---

## 6. Model Sağlayıcı Soyutlaması

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

## 7. Session State Şeması (özet — detay `ARCHITECTURE.md` §4)

```python
{
    "mode": "idle" | "collecting_batch",
    "dynamic_criteria": list[str] | None,
    "batch_cvs": list[tuple[CandidateProfile, pdf_file_name: str]],
}
```
