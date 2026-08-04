import re
from dataclasses import dataclass
from pathlib import Path

from models import CandidateProfile

# cwd'ye göre değil, bu dosyanın konumuna göre sabit — canlı testte cwd'ye bağlı
# göreli bir yol (bot repo kökünden mi src/ içinden mi başlatıldığına göre) iki
# farklı, birbirinden habersiz data/adaylar/ klasörü oluşturdu.
CANDIDATE_DIR = Path(__file__).resolve().parent.parent / "data" / "adaylar"


@dataclass
class CandidateDocument:
    name: str
    source_filename: str
    markdown: str


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "_", text)
    return text or "aday"


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- (belirtilmemiş)"
    return "\n".join(f"- {item}" for item in items)


def render_candidate_markdown(profile: CandidateProfile, source_filename: str) -> str:
    """CandidateProfile alanlarını Pydantic üzerinden yansımayla (reflection)
    dolaşır — modele alan eklenip çıkarıldıkça bu fonksiyon elle güncellenmeden
    otomatik ayak uydurur. Etiketler models.py'deki Field(description=...)
    metinlerinden gelir."""
    name = profile.full_name or source_filename
    summary_lines = [f"- Kaynak dosya: {source_filename}"]
    sections: list[str] = []

    for field_name, field_info in CandidateProfile.model_fields.items():
        if field_name == "full_name":
            continue
        value = getattr(profile, field_name)
        label = (field_info.json_schema_extra or {}).get("label", field_name)
        if isinstance(value, list):
            sections.append(f"## {label}\n{_bullet_list(value)}")
        else:
            summary_lines.append(f"- {label}: {value if value is not None else '(belirtilmemiş)'}")

    return f"# {name}\n\n" + "\n".join(summary_lines) + "\n\n" + "\n\n".join(sections) + "\n"


def write_candidate_markdown(profile: CandidateProfile, source_filename: str) -> Path:
    """ARCHITECTURE.md §6 — bilgi bankasına yazan taraf. Aynı isimde aday tekrar
    gönderilirse dosya güncellenir (üzerine yazılır) — v1'de bilinçli olarak
    çakışma/ayrım mantığı eklenmedi (KISS, kullanıcı geri bildirimi)."""
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(profile.full_name or source_filename)
    path = CANDIDATE_DIR / f"{slug}.md"
    path.write_text(render_candidate_markdown(profile, source_filename), encoding="utf-8")
    return path


def load_candidate_document(path: Path) -> CandidateDocument | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if not text:
        return None
    first_line = text.splitlines()[0]
    name = first_line.removeprefix("# ").strip() or path.stem
    source_filename = path.stem
    for line in text.splitlines():
        if line.startswith("- Kaynak dosya:"):
            source_filename = line.split(":", 1)[1].strip()
            break
    return CandidateDocument(name=name, source_filename=source_filename, markdown=text)


def list_all_candidates() -> list[CandidateDocument]:
    """Bilgi bankasındaki TÜM adayları deterministik olarak (LLM'siz) okur.
    `evaluate_candidates`'ın scope_hint verilmediği en yaygın senaryoda kullanılır
    — ödevin çekirdek gereksinimi bu, agentic aramaya bağımlı değil."""
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    docs = []
    for path in sorted(CANDIDATE_DIR.glob("*.md")):
        doc = load_candidate_document(path)
        if doc:
            docs.append(doc)
    return docs


def find_candidates_by_hint(hint: str) -> list[CandidateDocument]:
    """scope_hint metnindeki kelimelerle aday adları arasında kesişim arar —
    LLM'siz, deterministik. ARCHITECTURE.md §9.3: `FilesystemContextProvider.aquery()`
    canlı testte `Answer.results`'ı boş döndürdü (bulduğu cevabı `Answer.text`'e
    sentezlemiş, ham `Document` listesine değil) — bu yüzden agentic aramadan
    tamamen vazgeçildi, ölçek (birkaç test adayı) zaten buna gerek bırakmıyor.

    Tam kelime eşleşmesi değil, önek (prefix) kontrolü — Türkçe hâl ekleri
    ("Kazım" -> "Kazımı", "Kazım'a") tam eşleşmeyi kırıyor, önek her iki yönde
    de bunu tolere ediyor. 3 karakterden kısa kelimeler yanlış pozitifi
    azaltmak için elenir."""
    hint_words = [w for w in hint.casefold().split() if len(w) >= 3]
    if not hint_words:
        return []
    matches = []
    for doc in list_all_candidates():
        name_words = [w for w in doc.name.casefold().split() if len(w) >= 3]
        if any(h.startswith(n) or n.startswith(h) for h in hint_words for n in name_words):
            matches.append(doc)
    return matches
