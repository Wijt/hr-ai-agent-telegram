"""Kayıtlı adaylar üzerinde analiz (ör. SWOT, kriter bazlı puanlama) üreten tool'lar.

Alım hattından (cv_intake.py) ayrı tutuluyor: burası sorgu zamanında, zaten
knowledgebase'de duran adaylar üzerinde çalışıyor, dosya kaydetme işiyle ilgisi yok.

score_cv_against_criteria/score_multiple_candidates prensibi: tool'lar YAPILANDIRILMIŞ
VERİ (JSON) döner, hazır mesaj değil — kullanıcıya nasıl sunulacağına çağıran chat agent
karar verir (bkz. main.py'deki instructions).
"""

import asyncio
import json
from typing import Optional

from agno.agent import Agent

from cv_intake import KNOWLEDGE_DIR
from models.model_factory import get_model
from schemas import CandidateScoreReport, SWOTAnalysis

swot_agent = Agent(
    name="CV SWOT Analyst",
    model=get_model(),
    instructions=(
        "Sana bir adayın normalize edilmiş CV verisi (JSON) verilecek. Bu veriye dayanarak "
        "objektif bir SWOT analizi yap: strengths (güçlü yönler), weaknesses (gelişime açık "
        "yönler), opportunities (bu profile uygun fırsatlar/roller), threats (riskler, ör. "
        "eksik sertifika, dar teknoloji yelpazesi, deneyim boşlukları). Her kategori için "
        "2-5 madde yaz, kısa ve somut olsun, CV'deki gerçek bilgilere dayansın, uydurma yapma."
    ),
    output_schema=SWOTAnalysis,
)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (belirtilmedi)"


# TODO: score_cv_against_criteria/score_multiple_candidates ile aynı mimariye çekilmeli:
# bu tool kendi markdown'ını üretiyor (return'daki f-string), oysa yeni prensibimiz "tool'lar
# veri döner, mesajı çağıran chat agent oluşturur". Doğru hal: analyze_cv_swot da SWOTAnalysis'i
# JSON string olarak dönmeli (bkz. score_cv_against_criteria), main.py'deki agent instructions'ı
# da SWOT sonucunu kendisi markdown'a çevirecek şekilde güncellenmeli. candidate_id çözümlemesi
# de (hangi adaydan bahsediliyor, belirsizse sor) diğer tool'larla aynı konuşma-bağlamlı mantığa
# taşınmalı. Şimdilik dokunulmuyor — mevcut davranış korunuyor, ayrı bir adımda ele alınacak.
async def analyze_cv_swot(candidate_id: str) -> str:
    """Kayıtlı bir adayın CV'sine dayanan SWOT analizi (güçlü/zayıf yönler, fırsatlar,
    tehditler) üretir. Kullanıcı bir adayın SWOT analizini istediğinde çağır.

    Args:
        candidate_id: Analiz edilecek adayın candidate_id'si (klasör adı, ör. 'furkan_kaya').
            Önce list_files/grep_file ile doğru candidate_id'yi bul.
    """
    normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
    if not normalized_path.exists():
        return f"'{candidate_id}' adında kayıtlı bir aday bulunamadı."

    cv_json = normalized_path.read_text(encoding="utf-8")
    run_output = await swot_agent.arun(input=cv_json)
    analysis = run_output.content
    if not isinstance(analysis, SWOTAnalysis):
        return "SWOT analizi üretilemedi."

    return (
        f"**SWOT Analizi — {candidate_id}**\n\n"
        f"**Güçlü Yönler**\n{_bullets(analysis.strengths)}\n\n"
        f"**Zayıf Yönler**\n{_bullets(analysis.weaknesses)}\n\n"
        f"**Fırsatlar**\n{_bullets(analysis.opportunities)}\n\n"
        f"**Tehditler**\n{_bullets(analysis.threats)}"
    )


scoring_agent = Agent(
    name="CV Criteria Scorer",
    model=get_model(),
    instructions=(
        "Sana bir adayın normalize edilmiş CV verisi (JSON) ve kullanıcının belirlediği "
        "değerlendirme kriterleri verilecek. Her kriter için 0-100 arası bir puan ver "
        "(kısa bir gerekçeyle) — kriterle ilgili veri yoksa düşük puan ver ve gerekçede "
        "bunu belirt, uydurma yapma. Ardından bu kriterlere göre genel güçlü yönler, "
        "zayıf yönler ve gelişim tavsiyeleri yaz. Son olarak tek cümlelik bir İK "
        "değerlendirmesi yaz. Sadece CV'deki gerçek bilgilere dayan."
    ),
    output_schema=CandidateScoreReport,
)


async def _score_candidate(candidate_id: str, criteria: list[str]) -> Optional[dict]:
    """Tek bir adayı verilen kriterlere göre puanlar; hem score_cv_against_criteria hem
    score_multiple_candidates bu ortak mantığı kullanır. Aday yoksa None döner.
    """
    normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
    if not normalized_path.exists():
        return None

    cv_json = normalized_path.read_text(encoding="utf-8")
    criteria_listing = "\n".join(f"- {c}" for c in criteria)
    prompt = f"Değerlendirme kriterleri:\n{criteria_listing}\n\nCV verisi (JSON):\n{cv_json}"

    run_output = await scoring_agent.arun(input=prompt)
    report = run_output.content
    if not isinstance(report, CandidateScoreReport) or not report.scores:
        return None

    # Ortalamayı LLM'e hesaplatmıyoruz — LLM'ler aritmetikte güvenilmez, bu deterministik.
    average_score = round(sum(s.score for s in report.scores) / len(report.scores), 1)
    cv_data = json.loads(cv_json)
    candidate_name = (cv_data.get("personal_info") or {}).get("full_name") or candidate_id

    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "scores": {s.criterion: s.score for s in report.scores},
        "average_score": average_score,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "development_suggestions": report.development_suggestions,
        "hr_evaluation": report.hr_evaluation,
    }


async def score_cv_against_criteria(candidate_id: str, criteria: list[str]) -> str:
    """Bir adayı kullanıcının belirlediği kriterlere göre puanlar. YAPILANDIRILMIŞ VERİ
    (JSON) döner — hazır bir mesaj DEĞİLDİR; sonucu okunaklı bir markdown'a çevirip
    kullanıcıya sunmak çağıran agent'ın işidir, ham JSON'u kullanıcıya gösterme.

    Args:
        candidate_id: Puanlanacak adayın candidate_id'si.
        criteria: Kullanıcının belirlediği değerlendirme kriterleri (ör.
            ["React tecrübesi", "Clean Code", "Uzaktan çalışma uyumu"]).
    """
    result = await _score_candidate(candidate_id, criteria)
    if result is None:
        return json.dumps(
            {"status": "error", "message": f"'{candidate_id}' adında kayıtlı bir aday bulunamadı."},
            ensure_ascii=False,
        )
    return json.dumps({"status": "success", **result}, ensure_ascii=False, indent=2)


async def score_multiple_candidates(candidate_ids: list[str], criteria: list[str]) -> str:
    """Birden fazla adayı aynı kriterlere göre puanlar, ortalama puana göre sıralar ve en
    yüksek puanlı ilk 3 adayı döner. YAPILANDIRILMIŞ VERİ (JSON) döner — hazır bir mesaj
    DEĞİLDİR; sonucu okunaklı bir markdown'a (sıralı liste vb.) çevirip kullanıcıya
    sunmak çağıran agent'ın işidir, ham JSON'u kullanıcıya gösterme.

    Args:
        candidate_ids: Puanlanacak adayların candidate_id listesi.
        criteria: Kullanıcının belirlediği değerlendirme kriterleri.
    """
    results = await asyncio.gather(*(_score_candidate(cid, criteria) for cid in candidate_ids))
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
        normalized_path = KNOWLEDGE_DIR / candidate_id / f"{candidate_id}_normalized.json"
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
