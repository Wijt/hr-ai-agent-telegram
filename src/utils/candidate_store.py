"""Aday knowledgebase'inin ortak katmanı: dizin yapısı, kalıcı yazma ve bekleyen
duplicate kayıt kararları.

Hem alım hattı (cv_intake.py) hem tools/ altındaki tool'lar burayı kullanır — aday
dosyalarının nerede ve hangi isimle durduğu bilgisinin iki yerde elle yazılmaması için.
"""

import json
import time
from typing import Optional

from agno.media import File
from pathlib import Path
from slugify import slugify as _slugify_lib

from config import DATA_DIR
from schemas import CVIntake

KNOWLEDGE_DIR = DATA_DIR / "knowledgebase" / "adaylar"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

# Aynı isimde zaten kayıtlı bir aday bulunduğunda, persist etmeden önce kullanıcıya
# güncelle/yeni-kayıt/vazgeç diye sorulur; cevap gelene kadar bekleyen karar burada tutulur.
# Birden fazla CV aynı anda duplicate çıkabildiği için session başına LİSTE tutuluyor —
# tek bir slot olsaydı ikinci bir soru ilkini sessizce ezerdi.
pending_duplicate_decisions: dict[str, list[dict]] = {}
PENDING_DECISION_TTL_SECONDS = 30 * 60


def sweep_stale_decisions() -> None:
    """Cevapsız kalan kayıt kararlarını süresi dolunca düşürür.

    /new yeni bir session_id üretiyor ve agent'a hiç uğramıyor (Telegram router'ı komutu
    agent.arun'dan önce kesiyor), yani o session'a bağlı bekleyen karar bir daha ne
    çözülebiliyor ne iptal edilebiliyor — ama sözlükte, içindeki File nesnesiyle (ham PDF
    byte'ları) birlikte kalıyordu. Kullanıcı normal akışta devam ederse zaten oto-iptal
    devreye giriyor; bu süpürme sadece hiç mesaj yazmadan /new denen durum için.
    """
    now = time.monotonic()
    for sid in list(pending_duplicate_decisions):
        fresh = [
            p
            for p in pending_duplicate_decisions[sid]
            if now - p["created_at"] < PENDING_DECISION_TTL_SECONDS
        ]
        if fresh:
            pending_duplicate_decisions[sid] = fresh
        else:
            del pending_duplicate_decisions[sid]


def candidate_slug(name: str) -> str:
    # python-slugify (Unidecode sarmalayıcı) sektör standardı transliterasyon: NFKD'nin
    # ayrıştıramadığı harfleri de (ı, ł, ø, ß, hatta Kiril/Yunan gibi Latin dışı
    # scriptleri) kapsar. Aynı adayın farklı yazımları (Kazım/Kazim) hep aynı
    # candidate_id'ye düşer.
    return _slugify_lib(name, separator="_") or "isimsiz_aday"


def normalized_json_path(candidate_id: str) -> Path:
    """Adayın normalize edilmiş CV verisinin (tek güvenilir kaynak) dosya yolu."""
    return KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"


def candidate_full_name(cv_data: dict, candidate_id: str) -> str:
    return (cv_data.get("personal_info") or {}).get("full_name") or candidate_id


def find_existing_candidate(email: Optional[str]) -> Optional[str]:
    """Email'i knowledgebase'deki TÜM adaylarla deterministik karşılaştırır.

    Daha önce bu aramayı cv_filer_agent kendi tool çağrılarıyla yapıyordu — küçük bir
    model N eşleşen dosyanın hepsini get_file ile okumayı atlayabiliyor ve bir sonraki
    adayı (ör. furkan_kaya_2) hiç kontrol etmeden 'eşleşme yok' diyebiliyordu. Email
    zaten CVIntake içinde çıkarılmış veri; ayrıca modele sordurmaya gerek yok.
    """
    email_norm = (email or "").strip().lower()
    if not email_norm:
        return None
    for path in KNOWLEDGE_DIR.glob("*/*_normalized.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        existing_email = (data.get("personal_info", {}).get("email") or "").strip().lower()
        if existing_email and existing_email == email_norm:
            return path.parent.name
    return None


def next_available_candidate_id(base_id: str) -> str:
    n = 2
    while (KNOWLEDGE_DIR / f"{base_id}_{n}").exists():
        n += 1
    return f"{base_id}_{n}"


def persist(intake: CVIntake, file: File, candidate_id: str) -> str:
    cv = intake.cv
    candidate_dir = KNOWLEDGE_DIR / candidate_id
    raw_dir = candidate_dir / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_bytes = file.content
    if not raw_bytes and file.filepath:
        raw_bytes = Path(file.filepath).read_bytes()
    if raw_bytes:
        (raw_dir / f"{candidate_id}_raw.pdf").write_bytes(raw_bytes)

    # Dosya adı da aday ismini taşımalı: FileSystemKnowledge.list_files sadece filename
    # veya rel_path'e göre fnmatch yapıyor, jenerik "normalized.json" isim bazlı aramada
    # hiç eşleşmiyordu.
    normalized_json_path(candidate_id).write_text(cv.model_dump_json(indent=2), encoding="utf-8")

    skills = ", ".join(cv.skills[:8]) if cv.skills else "belirtilmemiş"
    return (
        f"Aday kaydedildi: {candidate_id}. Ad: {cv.personal_info.full_name or 'bilinmiyor'}, "
        f"Unvan: {cv.personal_info.title or 'belirtilmemiş'}, Beceriler: {skills}"
    )
