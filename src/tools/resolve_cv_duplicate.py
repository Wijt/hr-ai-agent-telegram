"""Bekleyen duplicate-CV kayıt kararını sonuçlandıran tool.

Bekleyen kararların state'i (pending_duplicate_decisions) utils/candidate_store.py'de:
kararı OLUŞTURAN alım hattı (cv_intake.py) ile kararı ÇÖZEN bu tool aynı sözlüğü paylaşır.
"""

from typing import Literal

from agno.media import File
from agno.run import RunContext

from schemas import CVIntake
from utils.candidate_store import (
    next_available_candidate_id,
    pending_duplicate_decisions,
    persist,
)


def resolve_cv_duplicate(
    run_context: RunContext, filename: str, decision: Literal["update", "new", "cancel"]
) -> str:
    """Bekleyen bir CV kayıt kararını sonuçlandırır: mevcut kaydın üzerine yazar, ayrı bir
    kayıt olarak saklar ya da işlemden vazgeçer. Kullanıcı önceden sorulan
    'güncelle mi, yeni kayıt mı, vazgeçeyim mi' sorusuna cevap verdiğinde çağır.

    Args:
        filename: Kararın ait olduğu CV dosyasının adı (session'daki bekleyen kayıtlar
            listesinde gördüğün ile birebir aynı olmalı).
        decision: 'update' mevcut kaydı günceller, 'new' ayrı bir kayıt olarak saklar,
            'cancel' hiçbir şey yazmadan bekleyen kaydı düşürür (mevcut kayda dokunulmaz,
            yüklenen CV kaydedilmez).
    """
    session_id = run_context.session_id
    pending_list = pending_duplicate_decisions.get(session_id) if session_id else None
    if not pending_list:
        return "Bekleyen bir CV kayıt kararı bulunamadı."

    pending = next((p for p in pending_list if p["filename"] == filename), None)
    if pending is None:
        available = ", ".join(p["filename"] for p in pending_list)
        return f"'{filename}' için bekleyen bir kayıt bulunamadı. Bekleyen dosyalar: {available}"

    pending_list.remove(pending)
    if not pending_list:
        pending_duplicate_decisions.pop(session_id, None)

    intake: CVIntake = pending["intake"]
    file: File = pending["file"]
    candidate_id: str = pending["candidate_id"]

    if decision == "cancel":
        return (
            f"'{filename}' için kayıt işlemi iptal edildi: bu CV kaydedilmedi ve mevcut "
            f"'{candidate_id}' kaydına dokunulmadı."
        )
    if decision == "update":
        return persist(intake, file, candidate_id)
    new_id = next_available_candidate_id(candidate_id)
    return f"{persist(intake, file, new_id)} (Ayrı kayıt olarak saklandı.)"
