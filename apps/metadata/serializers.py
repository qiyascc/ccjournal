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
Metadata serileştiriciler — ccjournal'ın yapısal metadata'sını standart formatlara
çevirir. Hepsi lxml Element döndürür (well-formed, namespace'li).

Formatlar:
  * Dublin Core (oai_dc)  -> OAI-PMH zorunlu formatı
  * DataCite (kernel-4)   -> DOI tescili / zengin metadata
  * JATS                  -> makale XML standardı (front matter)
  * Crossref deposit      -> Crossref'e DOI kaydı (doi_batch)

Yapısal modelimiz (CRediT, ROR, ORCID, yapısal kaynakça, fon) sayesinde bu çıktılar
OJS'in EAV tabanlı üretiminden daha zengin ve güvenilirdir.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from django.conf import settings
from lxml import etree

NS = {
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "datacite": "http://datacite.org/schema/kernel-4",
    "crossref": "http://www.crossref.org/schema/5.3.1",
    "fr": "http://www.crossref.org/fundref.xsd",
    "xlink": "http://www.w3.org/1999/xlink",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _sub(parent, tag, text=None, **attrs):
    el = etree.SubElement(parent, tag, **attrs)
    if text is not None:
        el.text = str(text)
    return el


def _primary_t(pub):
    return (pub.translations.filter(locale=pub.primary_locale).first()
            or pub.translations.first())


def _public_url(pub) -> str:
    base = getattr(settings, "SITE_URL", "https://example.org")
    try:
        from apps.configuration.services import Config
        base = Config.get("general", "site_url", base)
    except Exception:
        pass
    return f"{base.rstrip('/')}/article/{pub.submission_id}"


def _split_date(d):
    if isinstance(d, dt.datetime):
        d = d.date()
    return (d.year, d.month, d.day) if d else (None, None, None)


def to_dublin_core(pub):
    root = etree.Element(
        _q("oai_dc", "dc"),
        {_q("xsi", "schemaLocation"):
            "http://www.openarchives.org/OAI/2.0/oai_dc/ "
            "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"},
        nsmap={"oai_dc": NS["oai_dc"], "dc": NS["dc"], "xsi": NS["xsi"]},
    )
    journal = pub.submission.journal
    jt = journal.tr()

    for t in pub.translations.all():
        title = t.title + (f": {t.subtitle}" if t.subtitle else "")
        _sub(root, _q("dc", "title"), title, **{_q("xml", "lang"): t.locale})
    for a in pub.authors.all().order_by("seq"):
        name = f"{a.family_name}, {a.given_name}".strip(", ")
        _sub(root, _q("dc", "creator"), name)
    for kw in pub.keywords.all():
        _sub(root, _q("dc", "subject"), kw.term, **{_q("xml", "lang"): kw.locale})
    for t in pub.translations.exclude(abstract=""):
        _sub(root, _q("dc", "description"), t.abstract, **{_q("xml", "lang"): t.locale})
    if journal.publisher:
        _sub(root, _q("dc", "publisher"), journal.publisher)
    if pub.date_published:
        _sub(root, _q("dc", "date"), pub.date_published.isoformat())
    _sub(root, _q("dc", "type"), "info:eu-repo/semantics/article")
    _sub(root, _q("dc", "type"), "Text")
    for g in pub.galleys.all():
        if g.file and g.file.mimetype:
            _sub(root, _q("dc", "format"), g.file.mimetype)
    if pub.doi_id:
        _sub(root, _q("dc", "identifier"), pub.doi.url)
    _sub(root, _q("dc", "identifier"), _public_url(pub))
    if jt:
        src = jt.title + (f"; {journal.issn_online}" if journal.issn_online else "")
        _sub(root, _q("dc", "source"), src)
    _sub(root, _q("dc", "language"), pub.primary_locale)
    if pub.doi_id and pub.source_publication_id:
        _sub(root, _q("dc", "relation"), pub.doi.url)
    if pub.license_url:
        _sub(root, _q("dc", "rights"), pub.license_url)
    return root


def to_datacite(pub):
    root = etree.Element(
        _q("datacite", "resource"),
        {_q("xsi", "schemaLocation"):
            "http://datacite.org/schema/kernel-4 "
            "http://schema.datacite.org/meta/kernel-4.4/metadata.xsd"},
        nsmap={None: NS["datacite"], "xsi": NS["xsi"]},
    )
    journal = pub.submission.journal
    pt = _primary_t(pub)

    ident = _sub(root, _q("datacite", "identifier"),
                 pub.doi.doi if pub.doi_id else _public_url(pub))
    ident.set("identifierType", "DOI" if pub.doi_id else "URL")

    creators = _sub(root, _q("datacite", "creators"))
    for a in pub.authors.all().order_by("seq"):
        c = _sub(creators, _q("datacite", "creator"))
        _sub(c, _q("datacite", "creatorName"),
             f"{a.family_name}, {a.given_name}".strip(", "),
             nameType="Personal")
        if a.given_name:
            _sub(c, _q("datacite", "givenName"), a.given_name)
        if a.family_name:
            _sub(c, _q("datacite", "familyName"), a.family_name)
        if a.orcid:
            nid = _sub(c, _q("datacite", "nameIdentifier"), f"https://orcid.org/{a.orcid}")
            nid.set("nameIdentifierScheme", "ORCID")
            nid.set("schemeURI", "https://orcid.org")
        if a.affiliation:
            aff = _sub(c, _q("datacite", "affiliation"), a.affiliation)
            if a.affiliation_ror:
                aff.set("affiliationIdentifier", a.affiliation_ror)
                aff.set("affiliationIdentifierScheme", "ROR")

    titles = _sub(root, _q("datacite", "titles"))
    for t in pub.translations.all():
        _sub(titles, _q("datacite", "title"), t.title, **{_q("xml", "lang"): t.locale})
        if t.subtitle:
            st = _sub(titles, _q("datacite", "title"), t.subtitle, **{_q("xml", "lang"): t.locale})
            st.set("titleType", "Subtitle")

    _sub(root, _q("datacite", "publisher"), journal.publisher or (journal.tr().title if journal.tr() else journal.path))
    year = (pub.date_published.year if pub.date_published else dt.date.today().year)
    _sub(root, _q("datacite", "publicationYear"), year)

    rt = _sub(root, _q("datacite", "resourceType"), "Journal Article")
    rt.set("resourceTypeGeneral", "JournalArticle")

    if pub.keywords.exists():
        subs = _sub(root, _q("datacite", "subjects"))
        for kw in pub.keywords.all():
            _sub(subs, _q("datacite", "subject"), kw.term, **{_q("xml", "lang"): kw.locale})

    _sub(root, _q("datacite", "language"), pub.primary_locale)

    if pt and any(t.abstract for t in pub.translations.all()):
        descs = _sub(root, _q("datacite", "descriptions"))
        for t in pub.translations.exclude(abstract=""):
            d = _sub(descs, _q("datacite", "description"), t.abstract, **{_q("xml", "lang"): t.locale})
            d.set("descriptionType", "Abstract")

    if pub.license_url:
        rl = _sub(root, _q("datacite", "rightsList"))
        _sub(rl, _q("datacite", "rights"), "", rightsURI=pub.license_url)

    if pub.funders.exists():
        fr = _sub(root, _q("datacite", "fundingReferences"))
        for f in pub.funders.all():
            ref = _sub(fr, _q("datacite", "fundingReference"))
            _sub(ref, _q("datacite", "funderName"), f.funder_name)
            if f.funder_id:
                fid = _sub(ref, _q("datacite", "funderIdentifier"), f.funder_id)
                fid.set("funderIdentifierType", "ROR" if "ror.org" in f.funder_id else "Crossref Funder ID")
            for award in (f.award_numbers or []):
                _sub(ref, _q("datacite", "awardNumber"), award)
    return root


def to_jats(pub):
    journal = pub.submission.journal
    jt = journal.tr()
    article = etree.Element("article", {"article-type": "research-article"},
                            nsmap={"xlink": NS["xlink"]})
    front = _sub(article, "front")

    jmeta = _sub(front, "journal-meta")
    _sub(jmeta, "journal-id", journal.path, **{"journal-id-type": "publisher"})
    jtg = _sub(jmeta, "journal-title-group")
    if jt:
        _sub(jtg, "journal-title", jt.title)
    if journal.issn_online:
        _sub(jmeta, "issn", journal.issn_online, **{"pub-type": "epub"})
    if journal.publisher:
        _sub(_sub(jmeta, "publisher"), "publisher-name", journal.publisher)

    ameta = _sub(front, "article-meta")
    if pub.doi_id:
        _sub(ameta, "article-id", pub.doi.doi, **{"pub-id-type": "doi"})
    if pub.section:
        cats = _sub(ameta, "article-categories")
        sg = _sub(cats, "subj-group", **{"subj-group-type": "heading"})
        _sub(sg, "subject", pub.section.tr_value("title"))

    tg = _sub(ameta, "title-group")
    pt = _primary_t(pub)
    if pt:
        _sub(tg, "article-title", pt.title, **{_q("xml", "lang"): pt.locale})
        if pt.subtitle:
            _sub(tg, "subtitle", pt.subtitle)
    for t in pub.translations.exclude(pk=(pt.pk if pt else 0)):
        tt = _sub(tg, "trans-title-group", **{_q("xml", "lang"): t.locale})
        _sub(tt, "trans-title", t.title)

    cg = _sub(ameta, "contrib-group")
    for a in pub.authors.all().order_by("seq"):
        contrib = _sub(cg, "contrib", **{"contrib-type": "author"})
        if a.orcid:
            _sub(contrib, "contrib-id", f"https://orcid.org/{a.orcid}",
                 **{"contrib-id-type": "orcid"})
        nm = _sub(contrib, "name")
        _sub(nm, "surname", a.family_name)
        _sub(nm, "given-names", a.given_name)
        if a.affiliation:
            aff = _sub(contrib, "aff", a.affiliation)
            if a.affiliation_ror:
                _sub(aff, "institution-id", a.affiliation_ror,
                     **{"institution-id-type": "ror"})
        for role in (a.credit_roles or []):
            _sub(contrib, "role", role, vocab="credit",
                 **{"vocab-identifier": "https://credit.niso.org/"})

    if pub.date_published:
        y, m, d = _split_date(pub.date_published)
        pd = _sub(ameta, "pub-date", **{"date-type": "pub", "publication-format": "electronic"})
        _sub(pd, "day", d)
        _sub(pd, "month", m)
        _sub(pd, "year", y)
    iss = pub.issue
    if iss and iss.volume:
        _sub(ameta, "volume", iss.volume)
    if iss and iss.number:
        _sub(ameta, "issue", iss.number)
    if pub.pages and "-" in pub.pages:
        fp, lp = pub.pages.split("-", 1)
        _sub(ameta, "fpage", fp.strip())
        _sub(ameta, "lpage", lp.strip())

    if pub.license_url:
        perm = _sub(ameta, "permissions")
        if pub.copyright_holder:
            _sub(perm, "copyright-holder", pub.copyright_holder)
        if pub.copyright_year:
            _sub(perm, "copyright-year", pub.copyright_year)
        lic = _sub(perm, "license", **{_q("xlink", "href"): pub.license_url})
        _sub(lic, "license-p", pub.license_url)

    for t in pub.translations.exclude(abstract=""):
        ab = _sub(ameta, "abstract", **{_q("xml", "lang"): t.locale})
        _sub(ab, "p", t.abstract)

    if pub.keywords.exists():
        locales = {kw.locale for kw in pub.keywords.all()}
        for loc in locales:
            kg = _sub(ameta, "kwd-group", **{_q("xml", "lang"): loc})
            for kw in pub.keywords.filter(locale=loc):
                _sub(kg, "kwd", kw.term)

    if pub.funders.exists():
        fg = _sub(ameta, "funding-group")
        for f in pub.funders.all():
            ag = _sub(fg, "award-group")
            src = _sub(ag, "funding-source")
            inst = _sub(src, "institution-wrap")
            if f.funder_id:
                _sub(inst, "institution-id", f.funder_id,
                     **{"institution-id-type": "ror" if "ror.org" in f.funder_id else "doi"})
            _sub(inst, "institution", f.funder_name)
            for award in (f.award_numbers or []):
                _sub(ag, "award-id", award)

    if pub.citations.exists():
        back = _sub(article, "back")
        rl = _sub(back, "ref-list")
        for c in pub.citations.all().order_by("seq"):
            ref = _sub(rl, "ref", id=f"ref{c.seq or c.pk}")
            mc = _sub(ref, "mixed-citation", c.raw)
            if c.doi:
                _sub(mc, "pub-id", c.doi, **{"pub-id-type": "doi"})
    return article


def _crossmark_policy() -> str:
    """Crossmark politika DOI'si — [crossref] crossmark_policy_doi; boşsa kapalı.

    Ayarlıysa her makale deposit'ine crossmark bloğu eklenir; geri çekilmiş
    yayınlar kendi DOI'lerine 'retraction' update'i taşır (ayrı geri çekme
    duyurusu makalesi olmayan dergiler için kabul gören yerinde-güncelleme)."""
    try:
        from apps.configuration.services import Config
        return (Config.get("crossref", "crossmark_policy_doi", "") or "").strip()
    except Exception:
        return ""


def to_crossref_deposit(publications, *, depositor=None):
    """Birden çok yayını tek bir Crossref doi_batch içine paketler (DOI tescili)."""
    conf = getattr(settings, "CROSSREF", {})
    depositor = depositor or conf.get("depositor_name", "ccjournal")

    root = etree.Element(
        _q("crossref", "doi_batch"),
        {"version": "5.3.1",
         _q("xsi", "schemaLocation"):
            "http://www.crossref.org/schema/5.3.1 "
            "https://www.crossref.org/schemas/crossref5.3.1.xsd"},
        nsmap={None: NS["crossref"], "xsi": NS["xsi"], "fr": NS["fr"]},
    )
    head = _sub(root, _q("crossref", "head"))
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
    batch_id = hashlib.sha1(stamp.encode()).hexdigest()[:16]
    _sub(head, _q("crossref", "doi_batch_id"), batch_id)
    _sub(head, _q("crossref", "timestamp"), stamp)
    dep = _sub(head, _q("crossref", "depositor"))
    _sub(dep, _q("crossref", "depositor_name"), depositor)
    _sub(dep, _q("crossref", "email_address"), conf.get("depositor_email", "noreply@example.org"))
    _sub(head, _q("crossref", "registrant"), conf.get("registrant", depositor))

    body = _sub(root, _q("crossref", "body"))
    pubs = list(publications)
    if not pubs:
        return root

    journal = pubs[0].submission.journal
    jt = journal.tr()
    jel = _sub(body, _q("crossref", "journal"))
    jmeta = _sub(jel, _q("crossref", "journal_metadata"))
    if jt:
        _sub(jmeta, _q("crossref", "full_title"), jt.title)
        if jt.abbreviation:
            _sub(jmeta, _q("crossref", "abbrev_title"), jt.abbreviation)
    if journal.issn_online:
        _sub(jmeta, _q("crossref", "issn"), journal.issn_online, media_type="electronic")
    if journal.issn_print:
        _sub(jmeta, _q("crossref", "issn"), journal.issn_print, media_type="print")

    for pub in pubs:
        art = _sub(jel, _q("crossref", "journal_article"), publication_type="full_text")
        titles = _sub(art, _q("crossref", "titles"))
        pt = _primary_t(pub)
        if pt:
            _sub(titles, _q("crossref", "title"), pt.title)
            if pt.subtitle:
                _sub(titles, _q("crossref", "subtitle"), pt.subtitle)
        contribs = _sub(art, _q("crossref", "contributors"))
        for i, a in enumerate(pub.authors.all().order_by("seq")):
            pn = _sub(contribs, _q("crossref", "person_name"),
                      sequence="first" if i == 0 else "additional",
                      contributor_role="author")
            if a.given_name:
                _sub(pn, _q("crossref", "given_name"), a.given_name)
            _sub(pn, _q("crossref", "surname"), a.family_name or a.given_name)
            if a.affiliation:
                affs = _sub(pn, _q("crossref", "affiliations"))
                inst = _sub(affs, _q("crossref", "institution"))
                _sub(inst, _q("crossref", "institution_name"), a.affiliation)
                if a.affiliation_ror:
                    _sub(inst, _q("crossref", "institution_id"), a.affiliation_ror, type="ror")
            if a.orcid:
                _sub(pn, _q("crossref", "ORCID"), f"https://orcid.org/{a.orcid}")
        if pub.date_published:
            y, m, d = _split_date(pub.date_published)
            pdate = _sub(art, _q("crossref", "publication_date"), media_type="online")
            _sub(pdate, _q("crossref", "month"), f"{m:02d}")
            _sub(pdate, _q("crossref", "day"), f"{d:02d}")
            _sub(pdate, _q("crossref", "year"), y)
        if pub.pages and "-" in pub.pages:
            fp, lp = pub.pages.split("-", 1)
            pg = _sub(art, _q("crossref", "pages"))
            _sub(pg, _q("crossref", "first_page"), fp.strip())
            _sub(pg, _q("crossref", "last_page"), lp.strip())
        if pub.funders.exists():
            prog = _sub(art, _q("fr", "program"), name="fundref")
            for f in pub.funders.all():
                ga = _sub(prog, _q("fr", "assertion"), name="fundgroup")
                fn = _sub(ga, _q("fr", "assertion"), f.funder_name, name="funder_name")
                if f.funder_id:
                    _sub(fn, _q("fr", "assertion"), f.funder_id, name="funder_identifier")
                for award in (f.award_numbers or []):
                    _sub(ga, _q("fr", "assertion"), award, name="award_number")
        policy = _crossmark_policy()
        if policy and pub.doi_id:
            cm = _sub(art, _q("crossref", "crossmark"))
            _sub(cm, _q("crossref", "crossmark_version"), "2")
            _sub(cm, _q("crossref", "crossmark_policy"), policy)
            if getattr(pub, "retracted_at", None):
                ups = _sub(cm, _q("crossref", "updates"))
                _sub(ups, _q("crossref", "update"), pub.doi.doi,
                     type="retraction", date=pub.retracted_at.isoformat())
        if pub.doi_id:
            dd = _sub(art, _q("crossref", "doi_data"))
            _sub(dd, _q("crossref", "doi"), pub.doi.doi)
            _sub(dd, _q("crossref", "resource"), _public_url(pub))
        if pub.citations.exists():
            cl = _sub(art, _q("crossref", "citation_list"))
            for c in pub.citations.all().order_by("seq"):
                cit = _sub(cl, _q("crossref", "citation"), key=f"ref{c.seq or c.pk}")
                if c.doi:
                    _sub(cit, _q("crossref", "doi"), c.doi)
                _sub(cit, _q("crossref", "unstructured_citation"), c.raw)
    return root


OAI_FORMATS = {
    "oai_dc": {
        "namespace": NS["oai_dc"],
        "schema": "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        "builder": to_dublin_core,
    },
    "datacite": {
        "namespace": NS["datacite"],
        "schema": "http://schema.datacite.org/meta/kernel-4.4/metadata.xsd",
        "builder": to_datacite,
    },
    "jats": {
        "namespace": "https://jats.nlm.nih.gov/publishing/1.3/",
        "schema": "https://jats.nlm.nih.gov/publishing/1.3/xsd/JATS-journalpublishing1-3.xsd",
        "builder": to_jats,
    },
}
