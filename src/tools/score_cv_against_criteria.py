"""Tek adayı kullanıcı kriterlerine göre puanlayan tool. Puanlama çekirdeği
(scoring_agent + score_candidate) score_multiple_candidates ile ortak olduğu için
utils/scoring.py'de yaşıyor.
"""

import json

from utils.scoring import score_candidate


async def score_cv_against_criteria(candidate_id: str, criteria: list[str]) -> str:
    """Bir adayı kullanıcının belirlediği kriterlere göre puanlar. YAPILANDIRILMIŞ VERİ
    (JSON) döner — hazır bir mesaj DEĞİLDİR; sonucu okunaklı bir markdown'a çevirip
    kullanıcıya sunmak çağıran agent'ın işidir, ham JSON'u kullanıcıya gösterme.

    Args:
        candidate_id: Puanlanacak adayın candidate_id'si.
        criteria: Kullanıcının belirlediği değerlendirme kriterleri (ör.
            ["React tecrübesi", "Clean Code", "Uzaktan çalışma uyumu"]).
    """
    result = await score_candidate(candidate_id, criteria)
    if result is None:
        return json.dumps(
            {"status": "error", "message": f"'{candidate_id}' adında kayıtlı bir aday bulunamadı."},
            ensure_ascii=False,
        )
    return json.dumps({"status": "success", **result}, ensure_ascii=False, indent=2)
