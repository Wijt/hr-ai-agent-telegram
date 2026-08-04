# telegram-ai-hr-bot

Bu proje bir Telegram botudur. Bot yapay zeka kullanır. Kullanıcı bota serbest
metinle kriterler verir. Bot bu kriterlere göre CV'leri değerlendirir. Bot ayrıca
genel sohbet de yapar.

> Bu proje aktif geliştirme aşamasındadır. Mimari kararlar ve gerekçeleri için
> [ARCHITECTURE.md](./ARCHITECTURE.md)'ye bak. Ajan tasarımı için
> [AGENTS.md](./AGENTS.md)'ye bak. Çalışma ilkeleri (KISS, aşamalı geliştirme)
> `AGENTS.md` §0'dadır.

## Mimari

Tekli ve toplu CV işleme aynı pipeline'ı kullanır: `cv_processing_workflow`. Tekli
mod bu pipeline'ı bir kez çalıştırır. Toplu mod aynı pipeline'ı N aday için paralel
çalıştırır. Ayrıntılı gerekçe `ARCHITECTURE.md` §6'dadır. Ödevin bu tasarımı nasıl
gerektirdiğini `ARCHITECTURE.md` §3 ve §4 açıklar.

```mermaid
flowchart TB
    TG["Telegram (kullanıcı)"] --> RA["Router Agent<br/><i>pre_hook: dosya varsa submit_cv zorunlu</i>"]

    RA --> T1[set_dynamic_criteria]
    RA --> T2[start_batch_session]
    RA --> T3[submit_cv]
    RA --> T4[finalize_batch]

    T3 -->|"idle: hemen"| SCW["single_cv_workflow<br/>process + analyze_cv"]
    T3 -->|"batch: biriktir"| BUF[(session_state.batch_files)]
    T4 --> PAR["Parallel: N × ProcessAndScoreExecutor<br/>her dal ayrı bir dosya işler"]
    BUF -.-> T4

    SCW --> CPW
    PAR --> CPW["cv_processing_workflow — TEK paylaşılan tarif<br/>validate_pdf (stop=True kapısı) → extract_cv<br/>→ CandidateProfile"]

    CPW --> AN["analyze_cv → AnalysisAgent"]
    CPW --> SC["score → ScoringAgent (her dal)"]

    AN --> OUT1["Markdown rapor"]
    SC --> RANK["rank_top3<br/>ortalama + sıralama, LLM'siz"]
    RANK --> OUT2["JSON çıktısı (top 3)"]

    OUT1 --> DB[(SqliteDb: session_state + geçmiş)]
    OUT2 --> DB

    classDef single fill:#EEEDFE,stroke:#534AB7,color:#26215C
    classDef batch fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef shared fill:#FAEEDA,stroke:#854F0B,color:#412402
    class SCW,AN,OUT1 single
    class PAR,BUF,SC,RANK,OUT2 batch
    class CPW shared
```

## Durum

- [x] Proje deposu oluşturuldu
- [x] Mimari kararlar dokümante edildi (`ARCHITECTURE.md`, `AGENTS.md`)
- [x] **Aşama 0** — Hello World (Telegram bağlantısı, araçsız sohbet)
- [ ] **Aşama 1** — Sohbet + session (konuşma geçmişi)
- [ ] **Aşama 2** — Dinamik kriter + tekli CV analizi (`cv_processing_workflow`, PDF doğrulaması, extraction, analiz)
- [ ] **Aşama 3** — Toplu CV + paralel skorlama (JSON çıktı)
- [ ] *(opsiyonel)* Aşama 4 — Aday bilgi bankası
- [ ] *(opsiyonel)* Aşama 5 — Ollama, Docker

Aşamaların ayrıntısı ve başarı kriterleri `ARCHITECTURE.md` §13'tedir.
