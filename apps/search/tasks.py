# ==========================================================
#
# █▀█ █ █▄█ ▄▀█ █▀  █▀▀ █▀▀
# ▀▀█ █ ░█░ █▀█ ▄█  █▄▄ █▄▄
#
# Project     : CC Journal
# Developed by: Qiyas CC
# Copyright © 2026 Qiyas CC
# All Rights Reserved.
# ==========================================================

"""Kuyruğa uygun arama işleri (serialize-edilebilir argüman: submission_id)."""
from __future__ import annotations


def reindex(submission_id: int) -> dict:
    """Gönderinin güncel yayınını FTS'e indeksler (yoksa kaldırır)."""
    from apps.search.services import SearchIndex
    from apps.submissions.models import Submission

    sub = Submission.objects.filter(id=submission_id).first()
    if sub and sub.current_publication_id:
        SearchIndex.index(sub.current_publication)
        return {"indexed": submission_id}
    SearchIndex.remove(submission_id)
    return {"removed": submission_id}
