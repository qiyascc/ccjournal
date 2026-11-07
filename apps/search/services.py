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

"""
Tam-metin arama servisi (SQLite FTS5).

index/remove: yayın anında çağrılır (servis katmanından). search: sorgu -> submission
id listesi. FTS yoksa (örn. farklı DB) icontains'e düşülür.
"""
from __future__ import annotations

from django.db import connection

_FOLD = str.maketrans({
    "ə": "e", "Ə": "e", "ı": "i", "İ": "i", "ş": "s", "Ş": "s",
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ö": "o", "Ö": "o",
    "ü": "u", "Ü": "u", "â": "a", "î": "i", "û": "u",
})


def fold(text: str) -> str:
    return (text or "").translate(_FOLD).lower()


def _fts_available() -> bool:
    if connection.vendor != "sqlite":
        return False
    with connection.cursor() as c:
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_index'")
        return c.fetchone() is not None


class SearchIndex:
    @staticmethod
    def index(publication) -> None:
        if not _fts_available():
            return
        sub_id = publication.submission_id
        title = fold(" ".join(t.title for t in publication.translations.all()))
        abstract = fold(" ".join((t.abstract or "") for t in publication.translations.all()))
        keywords = fold(" ".join(k.term for k in publication.keywords.all()))
        authors = fold(" ".join(f"{a.given_name} {a.family_name}" for a in publication.authors.all()))
        with connection.cursor() as c:
            c.execute("DELETE FROM search_index WHERE rowid=%s", [sub_id])
            c.execute(
                "INSERT INTO search_index(rowid, title, abstract, keywords, authors) "
                "VALUES (%s,%s,%s,%s,%s)",
                [sub_id, title, abstract, keywords, authors],
            )

    @staticmethod
    def remove(submission_id: int) -> None:
        if not _fts_available():
            return
        with connection.cursor() as c:
            c.execute("DELETE FROM search_index WHERE rowid=%s", [submission_id])

    @staticmethod
    def search(query: str) -> list[int]:
        """Eşleşen submission id'lerini rank sırasıyla döndürür."""
        query = (query or "").strip()
        if not query:
            return []
        if not _fts_available():
            return SearchIndex._fallback(query)
        terms = [fold(t).replace('"', "") for t in query.split() if t.strip()]
        match = " ".join(f'"{t}"*' for t in terms)
        with connection.cursor() as c:
            try:
                c.execute(
                    "SELECT rowid FROM search_index WHERE search_index MATCH %s ORDER BY rank",
                    [match],
                )
                return [r[0] for r in c.fetchall()]
            except Exception:
                return SearchIndex._fallback(query)

    @staticmethod
    def _fallback(query: str) -> list[int]:
        from apps.publications.models import Publication, PublicationStatus
        return list(
            Publication.objects.filter(
                status=PublicationStatus.PUBLISHED,
                translations__title__icontains=query,
            ).values_list("submission_id", flat=True).distinct()
        )

    @staticmethod
    def rebuild() -> int:
        from apps.publications.models import Publication, PublicationStatus
        if _fts_available():
            with connection.cursor() as c:
                c.execute("DELETE FROM search_index")
        n = 0
        for pub in Publication.objects.filter(
                status=PublicationStatus.PUBLISHED).select_related("submission"):
            SearchIndex.index(pub)
            n += 1
        return n
