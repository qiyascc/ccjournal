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

"""OJS native XML içe aktarımı — `python manage.py import_ojs export.xml`.

OJS'in Tools → Import/Export → Native XML çıktısını (issue'lu veya yalın
article listesi) CC Journal'a taşır: sayı, bölüm, makale (başlık/özet çevirileri,
yazarlar, anahtar kelimeler, sayfalar, DOI) ve base64-gömülü galley dosyaları.
OJS 3.3/3.4 alan adı farkları (givenname/given_name) tolere edilir; ad alanı
(namespace) yok sayılır. DOI'si zaten kayıtlı makaleler atlanır (idempotent).
`--dry-run` hiçbir şey yazmaz, özet basar.
"""
from __future__ import annotations

import base64
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class _Rollback(Exception):
    pass


def _ln(el) -> str:
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _children(el, name):
    return [c for c in el if _ln(c) == name]


def _find(el, *names):
    cur = el
    for name in names:
        nxt = next((c for c in cur if _ln(c) == name), None)
        if nxt is None:
            return None
        cur = nxt
    return cur


def _text(el, *names, default="") -> str:
    node = _find(el, *names) if names else el
    return (node.text or "").strip() if node is not None else default


def _iter_deep(el, name):
    for c in el.iter():
        if _ln(c) == name:
            yield c


def _localized(el, name) -> dict[str, str]:
    """{locale: text} — locale attr'sız tek değer 'default' anahtarına düşer."""
    out: dict[str, str] = {}
    for node in _children(el, name):
        loc = (node.get("locale") or "default").split("_")[0]
        val = (node.text or "").strip()
        if val:
            out[loc] = val
    return out


class Command(BaseCommand):
    help = "Import an OJS native XML export (issues/articles) into this journal."

    def add_arguments(self, parser):
        parser.add_argument("xml_path")
        parser.add_argument("--dry-run", action="store_true",
                            help="Parse and report; write nothing.")

    def handle(self, *args, **opts):
        from lxml import etree

        path = Path(opts["xml_path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        try:
            root = etree.parse(str(path)).getroot()
        except etree.XMLSyntaxError as exc:
            raise CommandError(f"Not valid XML: {exc}") from exc

        from apps.journals.models import Journal
        journal = Journal.current()
        if not journal:
            raise CommandError("No journal configured — run /setup/ first.")

        self.stats = {"issues": 0, "articles": 0, "skipped": 0, "galleys": 0}
        try:
            with transaction.atomic():
                self._import_root(root, journal)
                if opts["dry_run"]:
                    raise _Rollback
        except _Rollback:
            self.stdout.write(self.style.WARNING("Dry run — nothing was saved."))
        s = self.stats
        self.stdout.write(self.style.SUCCESS(
            f"Issues: {s['issues']} · Articles imported: {s['articles']} · "
            f"skipped (already present): {s['skipped']} · galley files: {s['galleys']}"))

    # ------------------------------------------------------------------
    def _import_root(self, root, journal):
        tag = _ln(root)
        if tag == "issues":
            for issue_el in _children(root, "issue"):
                self._import_issue(issue_el, journal)
        elif tag == "issue":
            self._import_issue(root, journal)
        elif tag in ("articles", "article"):
            articles = [root] if tag == "article" else _children(root, "article")
            for a in articles:
                self._import_article(a, journal, issue=None, sections={})
        else:
            raise CommandError(
                f"Unsupported root element <{tag}> — expected an OJS native "
                "export (<issues>, <issue> or <articles>).")

    def _import_issue(self, issue_el, journal):
        from apps.journals.models import Issue, IssueTranslation

        ident = _find(issue_el, "issue_identification")
        if ident is None:
            ident = issue_el
        volume = _text(ident, "volume")
        number = _text(ident, "number")
        year = _text(ident, "year")
        titles = _localized(ident, "title")
        date_published = _text(issue_el, "date_published")

        issue, created = Issue.objects.get_or_create(
            journal=journal,
            volume=int(volume) if volume.isdigit() else None,
            number=number, year=int(year) if year.isdigit() else None,
            defaults={"primary_locale": journal.primary_locale})
        if date_published:
            from django.utils.dateparse import parse_date
            issue.is_published = True
            d = parse_date(date_published[:10])
            if d and not issue.date_published:
                from datetime import datetime, time
                from django.utils.timezone import make_aware
                issue.date_published = make_aware(datetime.combine(d, time.min))
            issue.save(update_fields=["is_published", "date_published"])
        for loc, title in titles.items():
            IssueTranslation.objects.get_or_create(
                issue=issue, locale=(journal.primary_locale if loc == "default" else loc),
                defaults={"title": title})
        self.stats["issues"] += 1

        sections = self._import_sections(issue_el, journal)
        for a in _iter_deep(issue_el, "article"):
            self._import_article(a, journal, issue=issue, sections=sections)

    def _import_sections(self, issue_el, journal) -> dict:
        from apps.journals.models import Section, SectionTranslation

        out: dict[str, object] = {}
        for sec_el in _iter_deep(issue_el, "section"):
            ref = _text(sec_el, "abbrev") or (sec_el.get("ref") or "")
            titles = _localized(sec_el, "title")
            title = (titles.get(journal.primary_locale) or titles.get("en")
                     or next(iter(titles.values()), "") or ref or "Articles")
            existing = None
            for s in journal.sections.all().prefetch_related("translations"):
                if any(t.title == title for t in s.translations.all()):
                    existing = s
                    break
            if existing is None:
                existing = Section.objects.create(
                    journal=journal, primary_locale=journal.primary_locale)
                SectionTranslation.objects.create(
                    section=existing, locale=journal.primary_locale, title=title)
            if ref:
                out[ref] = existing
        return out

    def _default_section(self, journal):
        from apps.journals.models import Section, SectionTranslation
        sec = journal.sections.first()
        if sec:
            return sec
        sec = Section.objects.create(journal=journal,
                                     primary_locale=journal.primary_locale)
        SectionTranslation.objects.create(section=sec, locale=journal.primary_locale,
                                          title="Articles")
        return sec

    def _import_article(self, art_el, journal, *, issue, sections):
        from django.utils.dateparse import parse_date

        from apps.core.models import Doi
        from apps.publications.models import (
            Author, Keyword, Publication, PublicationStatus, PublicationTranslation,
        )
        from apps.submissions.models import Stage, Submission, SubmissionStatus

        doi_value = ""
        for id_el in _iter_deep(art_el, "id"):
            if (id_el.get("type") or "").lower() == "doi":
                doi_value = (id_el.text or "").strip()
                break
        titles = _localized(art_el, "title")
        primary_title = (titles.get(journal.primary_locale) or titles.get("en")
                         or next(iter(titles.values()), ""))
        if doi_value and Doi.objects.filter(doi=doi_value).exists():
            self.stats["skipped"] += 1
            return
        if not doi_value and primary_title and PublicationTranslation.objects.filter(
                title=primary_title,
                publication__submission__journal=journal).exists():
            self.stats["skipped"] += 1
            return

        locale = (art_el.get("locale") or journal.primary_locale).split("_")[0]
        date_pub = parse_date((art_el.get("date_published")
                               or _text(art_el, "date_published"))[:10] or "")
        published = bool(date_pub) and (issue is None or issue.is_published)

        sub = Submission.objects.create(
            journal=journal, locale=locale, stage=Stage.PRODUCTION,
            status=(SubmissionStatus.PUBLISHED if published else SubmissionStatus.QUEUED))
        section = sections.get(art_el.get("section_ref") or "") \
            or self._default_section(journal)
        pub = Publication.objects.create(
            submission=sub, primary_locale=locale, section=section, issue=issue,
            pages=_text(art_el, "pages"),
            status=(PublicationStatus.PUBLISHED if published else PublicationStatus.QUEUED),
            date_published=date_pub)
        sub.current_publication = pub
        sub.save(update_fields=["current_publication"])

        abstracts = _localized(art_el, "abstract")
        locales = set(titles) | set(abstracts)
        for loc in (locales or {locale}):
            eff = locale if loc == "default" else loc
            PublicationTranslation.objects.update_or_create(
                publication=pub, locale=eff,
                defaults={"title": titles.get(loc, primary_title or "Untitled"),
                          "abstract": abstracts.get(loc, "")})

        for kw_parent in _iter_deep(art_el, "keywords"):
            for i, kw in enumerate(_children(kw_parent, "keyword")):
                term = (kw.text or "").strip()
                if term:
                    loc = (kw_parent.get("locale") or locale).split("_")[0]
                    Keyword.objects.create(publication=pub, locale=loc,
                                           term=term, seq=i)

        for i, a_el in enumerate(_iter_deep(art_el, "author")):
            given = (_localized(a_el, "givenname").get(locale)
                     or next(iter(_localized(a_el, "givenname").values()), "")
                     or _text(a_el, "given_name") or _text(a_el, "firstname"))
            family = (_localized(a_el, "familyname").get(locale)
                      or next(iter(_localized(a_el, "familyname").values()), "")
                      or _text(a_el, "family_name") or _text(a_el, "lastname"))
            if not (given or family):
                continue
            orcid = _text(a_el, "orcid").replace("https://orcid.org/", "").strip()
            affil = (_localized(a_el, "affiliation").get(locale)
                     or next(iter(_localized(a_el, "affiliation").values()), ""))
            author = Author.objects.create(
                publication=pub, given_name=given or family, family_name=family,
                email=_text(a_el, "email"), orcid=orcid, affiliation=affil, seq=i)
            if a_el.get("primary_contact") == "true" or i == 0:
                pub.primary_contact = author
                pub.save(update_fields=["primary_contact"])

        if doi_value:
            doi = Doi.objects.create(journal=journal, doi=doi_value)
            pub.doi = doi
            pub.save(update_fields=["doi"])

        self._import_galleys(art_el, sub, pub)
        if published:
            from apps.tasks.queue import enqueue_or_run
            enqueue_or_run("apps.search.tasks.reindex", sub.id)
        self.stats["articles"] += 1

    def _import_galleys(self, art_el, sub, pub):
        from django.core.files.base import ContentFile

        from apps.publications.models import Galley
        from apps.submissions.models import FileStage, SubmissionFile

        files: dict[str, tuple[str, bytes]] = {}
        for sf_el in _iter_deep(art_el, "submission_file"):
            fid = sf_el.get("id") or ""
            fname = ""
            data = b""
            for f_el in _iter_deep(sf_el, "file"):
                fname = f_el.get("filename") or fname
            for name_el in _iter_deep(sf_el, "name"):
                fname = fname or (name_el.text or "").strip()
            for emb in _iter_deep(sf_el, "embed"):
                try:
                    data = base64.b64decode((emb.text or "").strip())
                except Exception:
                    data = b""
            if fid and data:
                files[fid] = (fname or f"file-{fid}", data)

        for g_el in _iter_deep(art_el, "article_galley"):
            label = (next(iter(_localized(g_el, "name").values()), "") or "PDF")
            ref = None
            for r in _iter_deep(g_el, "submission_file_ref"):
                ref = r.get("id")
            got = files.get(ref or "")
            if not got:
                continue
            fname, data = got
            sf = SubmissionFile.objects.create(
                submission=sub, original_filename=fname,
                mimetype=("application/pdf" if fname.lower().endswith(".pdf") else ""),
                file_stage=FileStage.PRODUCTION_READY, file_size=len(data))
            sf.file.save(f"import/{sub.pk}-{fname}", ContentFile(data), save=True)
            Galley.objects.create(publication=pub, label=label, file=sf,
                                  is_approved=True,
                                  seq=(pub.galleys.count() + 1) * 1.0)
            self.stats["galleys"] += 1
