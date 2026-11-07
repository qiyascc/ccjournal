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
Atıf dışa aktarma — BibTeX ve RIS (OJS'te eklenti; burada çekirdekte).

/article/<pk>/cite.bib   → @article BibTeX kaydı
/article/<pk>/cite.ris   → RIS (EndNote/Zotero/Mendeley)
Reference manager'lar dosyayı doğrudan içe aktarır.
"""
from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from apps.submissions.models import Submission, SubmissionStatus

from .views import _content_locale, _journal_or_404


def _pub_and_meta(request, pk):
    journal = _journal_or_404()
    submission = get_object_or_404(
        Submission, pk=pk, journal=journal, status=SubmissionStatus.PUBLISHED)
    pub = submission.current_publication
    loc = _content_locale(request, journal)
    t = pub.tr(loc) if pub else None
    jt = journal.tr(loc)
    return {
        "submission": submission, "pub": pub,
        "title": (t.title if t else ""),
        "abstract": (t.abstract if t else ""),
        "journal_title": (jt.title if jt else journal.path),
        "authors": list(pub.authors.order_by("seq")) if pub else [],
        "keywords": list(pub.keywords.filter(locale=loc)
                         .values_list("term", flat=True)) if pub else [],
        "year": (pub.date_published.year if pub and pub.date_published else None),
        "volume": (pub.issue.volume if pub and pub.issue_id else None),
        "number": (pub.issue.number if pub and pub.issue_id else None),
        "pages": (pub.pages if pub else ""),
        "doi": (pub.doi.doi if pub and pub.doi_id else ""),
        "url": request.build_absolute_uri(f"/article/{submission.pk}/"),
        "issn": journal.issn_online or journal.issn_print or "",
    }


def _bib_escape(s: str) -> str:
    return (s or "").replace("{", "\\{").replace("}", "\\}").replace("\n", " ").strip()


def cite_bibtex(request, pk):
    m = _pub_and_meta(request, pk)
    authors = " and ".join(
        f"{a.family_name}, {a.given_name}".strip(", ") for a in m["authors"])
    lines = [f"@article{{ccj{m['submission'].pk},"]

    def add(field, value):
        if value:
            lines.append(f"  {field} = {{{_bib_escape(str(value))}}},")

    add("author", authors)
    add("title", m["title"])
    add("journal", m["journal_title"])
    add("year", m["year"])
    add("volume", m["volume"])
    add("number", m["number"])
    add("pages", (m["pages"] or "").replace("-", "--"))
    add("doi", m["doi"])
    add("issn", m["issn"])
    add("url", m["url"])
    add("abstract", m["abstract"])
    add("keywords", ", ".join(m["keywords"]))
    body = "\n".join(lines).rstrip(",") + "\n}\n"
    resp = HttpResponse(body, content_type="application/x-bibtex; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="citation-{pk}.bib"'
    return resp


def article_jats(request, pk):
    """Makalenin JATS XML kaydı — indeksleyiciler ve koruma için doğrudan link."""
    journal = _journal_or_404()
    submission = get_object_or_404(
        Submission, pk=pk, journal=journal, status=SubmissionStatus.PUBLISHED)
    from apps.publications.jats import jats_bytes
    resp = HttpResponse(jats_bytes(submission.current_publication),
                        content_type="application/xml; charset=utf-8")
    resp["Content-Disposition"] = f'inline; filename="article-{pk}-jats.xml"'
    return resp


def cite_ris(request, pk):
    m = _pub_and_meta(request, pk)
    lines = ["TY  - JOUR"]
    for a in m["authors"]:
        lines.append(f"AU  - {a.family_name}, {a.given_name}".strip(", "))
    lines.append(f"TI  - {m['title']}")
    lines.append(f"JO  - {m['journal_title']}")
    if m["year"]:
        lines.append(f"PY  - {m['year']}")
    if m["volume"]:
        lines.append(f"VL  - {m['volume']}")
    if m["number"]:
        lines.append(f"IS  - {m['number']}")
    pages = (m["pages"] or "")
    if "-" in pages:
        sp, _, ep = pages.partition("-")
        if sp.strip():
            lines.append(f"SP  - {sp.strip()}")
        if ep.strip():
            lines.append(f"EP  - {ep.strip()}")
    elif pages:
        lines.append(f"SP  - {pages}")
    if m["doi"]:
        lines.append(f"DO  - {m['doi']}")
    if m["issn"]:
        lines.append(f"SN  - {m['issn']}")
    lines.append(f"UR  - {m['url']}")
    if m["abstract"]:
        lines.append("AB  - " + m["abstract"].replace("\n", " ").strip())
    for kw in m["keywords"]:
        lines.append(f"KW  - {kw}")
    lines.append("ER  - ")
    resp = HttpResponse("\n".join(lines) + "\n",
                        content_type="application/x-research-info-systems; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="citation-{pk}.ris"'
    return resp
