"""Birden fazla adayı aynı kriterlerle puanlayıp sıralayan tool. Puanlama çekirdeği
(scoring_agent + score_candidate) score_cv_against_criteria ile ortak olduğu için
utils/scoring.py'de yaşıyor.
"""

import asyncio
import json

from utils.scoring import score_candidate


async def score_multiple_candidates(candidate_ids: list[str], criteria: list[str]) -> str:
    """Birden fazla adayı aynı kriterlere göre puanlar, ortalama puana göre sıralar ve en
    yüksek puanlı ilk 3 adayı döner. YAPILANDIRILMIŞ VERİ (JSON) döner — hazır bir mesaj
    DEĞİLDİR; sonucu okunaklı bir markdown'a (sıralı liste vb.) çevirip kullanıcıya
    sunmak çağıran agent'ın işidir, ham JSON'u kullanıcıya gösterme.

    Args:
        candidate_ids: Puanlanacak adayların candidate_id listesi.
        criteria: Kullanıcının belirlediği değerlendirme kriterleri.
    """
    results = await asyncio.gather(*(score_candidate(cid, criteria) for cid in candidate_ids))
    valid_results = [r for r in results if r is not None]
    valid_results.sort(key=lambda r: r["average_score"], reverse=True)
    top = valid_results[:3]

    top_candidates = [
        {
            "rank": i + 1,
            "candidateId": r["candidate_id"],
            "candidateName": r["candidate_name"],
            "dynamicScores": r["scores"],
            "averageScore": r["average_score"],
            "hrEvaluation": r["hr_evaluation"],
        }
        for i, r in enumerate(top)
    ]

    return json.dumps(
        {
            "status": "success",
            "processedCVCount": len(valid_results),
            "userDefinedCriteria": criteria,
            "topCandidates": top_candidates,
        },
        ensure_ascii=False,
        indent=2,
    )
