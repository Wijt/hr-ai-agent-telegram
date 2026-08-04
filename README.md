# telegram-ai-hr-bot

Yapay zeka destekli, dinamik kriterlere dayalı Telegram İK ve sohbet botu.

> Bu proje aktif geliştirme aşamasındadır. Mimari kararlar ve gerekçeleri için
> [ARCHITECTURE.md](./ARCHITECTURE.md) ve ajan tasarımı için [AGENTS.md](./AGENTS.md)
> dosyalarına bakınız. Çalışma ilkeleri (KISS, aşamalı geliştirme) `AGENTS.md` §0'da.
>
> **Yeni bir oturumdan devam ediyorsanız önce [TODO.md](./TODO.md)'yi okuyun** —
> güncel durum, operasyonel altyapı bilgisi ve somut sıradaki adımlar orada.

## Mimari

Yazan/okuyan ayrımına dayanır: CV'ler geldiğinde **otomatik** işlenip dosya
tabanlı bir bilgi bankasına (`data/adaylar/*.md`) yazılır; değerlendirme ise
**tamamen kullanıcı talebiyle**, o anki cümleden çıkarılan kriterlerle
tetiklenir — tekli/toplu ayrı tool'lar değil, bulunan aday sayısına göre kod
içinde dallanan tek bir akış. Detaylı gerekçe için `ARCHITECTURE.md` §6,
ödevin bunu nasıl gerektirdiği için §3/§4.

```mermaid
flowchart TB
    TG["Telegram (kullanıcı)"] --> RA["Router Agent<br/><i>pre_hook: dosya varsa submit_cv zorunlu</i>"]

    RA --> T1["submit_cv<br/>(PDF geldiğinde)"]
    RA --> T2["evaluate_candidates(criteria, scope_hint)<br/>(değerlendirme istendiğinde)"]

    T1 --> CPW["cv_intake.process_cv (düz fonksiyon)<br/>pdf_validator.validate → extraction_agent<br/>→ CandidateProfile"]
    CPW --> KB[("data/adaylar/*.md<br/>dosya tabanlı bilgi bankası")]

    T2 -->|"scope_hint boş"| ALL["list_all_candidates()<br/>deterministik, LLM'siz glob"]
    T2 -->|"scope_hint dolu"| FS["find_candidates_by_hint()<br/>önek eşleşmesi, LLM'siz"]
    ALL --> KB
    FS --> KB

    ALL --> N{"kaç aday<br/>bulundu?"}
    FS --> N
    N -->|"1"| AN["candidate_analysis.analyze_single"]
    N -->|"2+"| PAR["candidate_analysis.analyze_batch<br/>Workflow+Parallel: N × scoring_agent"]

    AN --> OUT1["Markdown rapor"]
    PAR --> RANK["rank adımı<br/>ortalama + sıralama, LLM'siz"]
    RANK --> OUT2["JSON çıktısı (top 3)"]

    OUT1 --> DB[(SqliteDb: sohbet geçmişi)]
    OUT2 --> DB

    classDef single fill:#EEEDFE,stroke:#534AB7,color:#26215C
    classDef batch fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef shared fill:#FAEEDA,stroke:#854F0B,color:#412402
    class AN,OUT1 single
    class PAR,RANK,OUT2 batch
    class CPW,KB,ALL,FS shared
```

## Durum

- [x] Proje deposu oluşturuldu
- [x] Mimari kararlar dokümante edildi (`ARCHITECTURE.md`, `AGENTS.md`)
- [x] **Aşama 0** — Hello World (Telegram bağlantısı, tool'suz sohbet)
- [x] **Aşama 1** — Sohbet + session (konuşma geçmişi, `SqliteDb`)
- [x] **Aşama 2** — Bilgi bankası + değerlendirme (`submit_cv`/`evaluate_candidates`,
      PDF validasyonu, extraction, tekli+toplu analiz) — kod tamam, canlı test bekliyor
- [ ] *(opsiyonel)* Aşama 3 — Ollama, Docker

Aşamaların detayı ve başarı kriterleri için `ARCHITECTURE.md` §13, güncel
durum ve canlı test adımları için [TODO.md](./TODO.md).
