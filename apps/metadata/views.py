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

"""OAI-PMH endpoint + Crossref deposit dışa aktarım view'ları."""
from __future__ import annotations

from lxml import etree

from django.http import HttpResponse, HttpResponseBadRequest

from apps.publications.models import Publication, PublicationStatus
from .oai import OAIProvider
from .serializers import to_crossref_deposit


def _xml_response(element, *, status=200) -> HttpResponse:
    body = etree.tostring(element, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    return HttpResponse(body, content_type="text/xml; charset=utf-8", status=status)


def oai(request) -> HttpResponse:
    """OAI-PMH 2.0 endpoint. GET ve POST (spec gereği ikisi de) desteklenir."""
    params = request.POST.dict() if request.method == "POST" else request.GET.dict()
    base_url = request.build_absolute_uri(request.path)
    provider = OAIProvider(base_url)
    return _xml_response(provider.handle(params))


def crossref_deposit(request) -> HttpResponse:
    """
    Seçili yayınlar için Crossref doi_batch üretir (DOI tescili).
    ?issue=<id>  veya  ?publication=<id>  ile filtrelenir; yoksa tüm yayımlananlar.
    """
    qs = Publication.objects.filter(status=PublicationStatus.PUBLISHED).select_related("submission")
    issue_id = request.GET.get("issue")
    pub_id = request.GET.get("publication")
    if issue_id:
        qs = qs.filter(issue_id=issue_id)
    if pub_id:
        qs = qs.filter(id=pub_id)
    pubs = list(qs)
    if not pubs:
        return HttpResponseBadRequest("No published publications match the filter.")
    el = to_crossref_deposit(pubs)
    resp = _xml_response(el)
    resp["Content-Disposition"] = 'attachment; filename="crossref-deposit.xml"'
    return resp


def pubmed_export(request) -> HttpResponse:
    """PubMed/MEDLINE publisher XML (ArticleSet) — staff indirir, NCBI'ye yükler.

    PubMed DTD'sinin zorunlu çekirdeğiyle sınırlı: dergi/ISSN/cilt/sayı/tarih,
    başlık, sayfalar, DOI, yazarlar, özet. ?issue=<id> ile filtrelenebilir.
    """
    if not (request.user.is_authenticated and request.user.is_staff):
        return HttpResponse(status=403)

    qs = (Publication.objects.filter(status=PublicationStatus.PUBLISHED)
          .select_related("submission__journal", "issue", "doi")
          .prefetch_related("translations", "authors"))
    if request.GET.get("issue"):
        qs = qs.filter(issue_id=request.GET["issue"])

    root = etree.Element("ArticleSet")
    for pub in qs:
        journal = pub.submission.journal
        jt = (journal.translations.filter(locale=journal.primary_locale).first()
              or journal.translations.first())
        t = (pub.translations.filter(locale=pub.primary_locale).first()
             or pub.translations.first())
        if not t:
            continue
        art = etree.SubElement(root, "Article")
        jel = etree.SubElement(art, "Journal")
        etree.SubElement(jel, "PublisherName").text = journal.publisher or ""
        etree.SubElement(jel, "JournalTitle").text = (jt.title if jt else journal.path)
        if journal.issn_online or journal.issn_print:
            etree.SubElement(jel, "Issn").text = journal.issn_online or journal.issn_print
        if pub.issue and pub.issue.volume:
            etree.SubElement(jel, "Volume").text = str(pub.issue.volume)
        if pub.issue and pub.issue.number:
            etree.SubElement(jel, "Issue").text = str(pub.issue.number)
        if pub.date_published:
            pd = etree.SubElement(jel, "PubDate", PubStatus="epublish")
            etree.SubElement(pd, "Year").text = str(pub.date_published.year)
            etree.SubElement(pd, "Month").text = str(pub.date_published.month)
            etree.SubElement(pd, "Day").text = str(pub.date_published.day)
        etree.SubElement(art, "ArticleTitle").text = t.title
        if pub.pages:
            sp, _, ep = pub.pages.partition("-")
            if sp.strip():
                etree.SubElement(art, "FirstPage").text = sp.strip()
            if ep.strip():
                etree.SubElement(art, "LastPage").text = ep.strip()
        if pub.doi_id:
            etree.SubElement(art, "ELocationID", EIdType="doi").text = pub.doi.doi
        alist = etree.SubElement(art, "AuthorList")
        for a in pub.authors.all():
            ael = etree.SubElement(alist, "Author")
            etree.SubElement(ael, "FirstName").text = a.given_name
            etree.SubElement(ael, "LastName").text = a.family_name or a.given_name
            if a.affiliation:
                etree.SubElement(ael, "Affiliation").text = a.affiliation
        if pub.doi_id:
            ids = etree.SubElement(art, "ArticleIdList")
            etree.SubElement(ids, "ArticleId", IdType="doi").text = pub.doi.doi
        if t.abstract:
            etree.SubElement(art, "Abstract").text = t.abstract

    body = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True,
        doctype='<!DOCTYPE ArticleSet PUBLIC "-//NLM//DTD PubMed 2.8//EN" '
                '"https://dtd.nlm.nih.gov/ncbi/pubmed/in/PubMed.dtd">')
    resp = HttpResponse(body, content_type="text/xml; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="pubmed-articles.xml"'
    return resp


def doaj_export(request) -> HttpResponse:
    """DOAJ toplu makale dışa aktarımı — bibjson biçiminde JSON dizisi.

    DOAJ'un article bulk-upload/API şemasıyla uyumlu; staff indirir ve DOAJ
    panelinden yükler (veya API'ye gönderir). ?issue=<id> ile filtrelenebilir.
    """
    import json

    if not (request.user.is_authenticated and request.user.is_staff):
        return HttpResponse(status=403)

    qs = (Publication.objects.filter(status=PublicationStatus.PUBLISHED)
          .select_related("submission__journal", "issue", "doi")
          .prefetch_related("translations", "authors", "keywords"))
    if request.GET.get("issue"):
        qs = qs.filter(issue_id=request.GET["issue"])

    out = []
    for pub in qs:
        journal = pub.submission.journal
        jt = (journal.translations.filter(locale=journal.primary_locale).first()
              or journal.translations.first())
        t = (pub.translations.filter(locale=pub.primary_locale).first()
             or pub.translations.first())
        if not t:
            continue
        bib = {
            "title": t.title,
            "abstract": t.abstract or "",
            "year": str(pub.date_published.year) if pub.date_published else "",
            "month": str(pub.date_published.month) if pub.date_published else "",
            "author": [{"name": f"{a.given_name} {a.family_name}".strip(),
                        **({"affiliation": a.affiliation} if a.affiliation else {}),
                        **({"orcid_id": f"https://orcid.org/{a.orcid}"} if a.orcid else {})}
                       for a in pub.authors.all()],
            "keywords": [k.term for k in pub.keywords.all()][:6],
            "journal": {
                "title": (jt.title if jt else journal.path),
                **({"volume": str(pub.issue.volume)} if pub.issue and pub.issue.volume else {}),
                **({"number": str(pub.issue.number)} if pub.issue and pub.issue.number else {}),
                **({"issns": [i for i in (journal.issn_online, journal.issn_print) if i]}
                   if (journal.issn_online or journal.issn_print) else {}),
            },
            "identifier": ([{"type": "doi", "id": pub.doi.doi}] if pub.doi_id else []),
            "link": [{"type": "fulltext", "url": request.build_absolute_uri(
                f"/article/{pub.submission_id}/")}],
        }
        if pub.pages:
            sp, _, ep = pub.pages.partition("-")
            if sp.strip():
                bib["start_page"] = sp.strip()
            if ep.strip():
                bib["end_page"] = ep.strip()
        out.append({"bibjson": bib})

    resp = HttpResponse(json.dumps(out, ensure_ascii=False, indent=2),
                        content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="doaj-articles.json"'
    return resp
