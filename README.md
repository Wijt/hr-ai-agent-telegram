# telegram-ai-hr-bot

Yapay zeka destekli, dinamik kriterlere dayalı Telegram İK ve sohbet botu.

> Bu proje aktif geliştirme aşamasındadır. Mimari kararlar ve gerekçeleri için
> [ARCHITECTURE.md](./ARCHITECTURE.md) ve ajan tasarımı için [AGENTS.md](./AGENTS.md)
> dosyalarına bakınız. Çalışma ilkeleri (KISS, aşamalı geliştirme) `AGENTS.md` §0'da.
>
> **Yeni bir oturumdan devam ediyorsanız önce [TODO.md](./TODO.md)'yi okuyun** —
> güncel durum, operasyonel altyapı bilgisi ve somut sıradaki adımlar orada.

## Mimari

Tekli ve toplu CV işleme, **tek bir paylaşılan pipeline'ı** (`cv_processing_workflow`)
kullanır — biri bir kez, öbürü N aday için paralel çalıştırır. Detaylı gerekçe için
`ARCHITECTURE.md` §6, ödevin bunu nasıl gerektirdiği için §3/§4.

```mermaid
flowchart TB
    TG["Telegram (kullanıcı)"] --> RA["Router Agent<br/><i>pre_hook: dosya varsa submit_cv zorunlu</i>"]

    RA --> T1[set_dynamic_criteria]
    RA --> T2[start_batch_session]
    RA --> T3[submit_cv]
    RA --> T4[finalize_batch]

    T3 -->|"idle: hemen"| CPW
    T3 -->|"batch: biriktir"| BUF[(session_state.batch_files)]
    T4 --> PAR["Parallel: N × process_and_score<br/>her dal ayrı bir dosya işler"]
    BUF -.-> T4

    PAR --> CPW["cv_processing_workflow — TEK paylaşılan tarif<br/>validate_pdf (stop=True kapısı) → extract_cv<br/>→ CandidateProfile"]

    CPW --> AN["AnalysisAgent (submit_cv içinde, tekli mod)"]
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
- [x] **Aşama 0** — Hello World (Telegram bağlantısı, tool'suz sohbet)
- [ ] **Aşama 1** — Sohbet + session (konuşma geçmişi)
- [ ] **Aşama 2** — Dinamik kriter + tekli CV analizi (`cv_processing_workflow`, PDF validasyonu, extraction, analiz)
- [ ] **Aşama 3** — Toplu CV + paralel skorlama (JSON çıktı)
- [ ] *(opsiyonel)* Aşama 4 — Aday bilgi bankası
- [ ] *(opsiyonel)* Aşama 5 — Ollama, Docker

Aşamaların detayı ve başarı kriterleri için `ARCHITECTURE.md` §13.
