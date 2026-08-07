"""İsim çakışmalarında ayırt edici kısa bilgi döndüren tool."""

import json

from utils.candidate_store import normalized_json_path


def summarize_candidates(candidate_ids: list[str]) -> str:
    """Verilen candidate_id'ler için KISA ayırt edici bilgi (ad, unvan, en son şirket)
    döner — tam CV değil. LLM çağırmaz, sadece dosyadan birkaç alan okur; get_file'dan
    çok daha ucuzdur. Aynı isimli birden fazla kayıt bulduğunda (isim çakışması),
    kullanıcıya hangisini kastettiğini BOŞ bir soruyla değil bu bilgiyle sor.

    Args:
        candidate_ids: Ayırt edilecek adayların candidate_id listesi.
    """
    summaries = []
    for candidate_id in candidate_ids:
        normalized_path = normalized_json_path(candidate_id)
        if not normalized_path.exists():
            continue
        data = json.loads(normalized_path.read_text(encoding="utf-8"))
        personal = data.get("personal_info") or {}
        work_experience = data.get("work_experience") or []
        latest_company = work_experience[0].get("company") if work_experience else None
        summaries.append(
            {
                "candidateId": candidate_id,
                "fullName": personal.get("full_name"),
                "title": personal.get("title"),
                "latestCompany": latest_company,
            }
        )
    return json.dumps(summaries, ensure_ascii=False, indent=2)
