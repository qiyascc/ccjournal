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

"""Kaskad başvuru paketi — ret sonrası taşınabilir makale arşivi.

Yazar, reddedilen çalışmasını TEK zip olarak indirir: package.json (tam
metadata), dosyalar ve yazara açık hakem yorumları. Başka bir CC Journal
kurulumu `manage.py import_ccj paket.zip` ile aynı çalışmayı saniyeler içinde
yeni başvuru olarak açar — yeniden biçimlendirme/yeniden yazım sıfır.
"""
from __future__ import annotations

import io
import json
import zipfile

PACKAGE_VERSION = 1


def build_package(submission) -> bytes:
    """Gönderiyi zip byte'ları olarak paketler."""
    pub = submission.current_publication
    meta = {
        "package": "ccjournal-submission",
        "version": PACKAGE_VERSION,
        "source_submission": submission.pk,
        "locale": submission.locale,
        "translations": [], "authors": [], "keywords": [],
        "suggested_reviewers": submission.suggested_reviewers or [],
        "files": [], "reviews": [],
    }
    if pub:
        for t in pub.translations.all():
            meta["translations"].append({
                "locale": t.locale, "title": t.title, "subtitle": t.subtitle,
                "abstract": t.abstract, "body": t.body})
        for a in pub.authors.order_by("seq"):
            meta["authors"].append({
                "given_name": a.given_name, "family_name": a.family_name,
                "email": a.email, "orcid": a.orcid, "affiliation": a.affiliation,
                "affiliation_ror": a.affiliation_ror,
                "credit_roles": list(a.credit_roles or [])})
        for k in pub.keywords.all():
            meta["keywords"].append({"locale": k.locale, "term": k.term})
        meta["data_availability"] = pub.data_availability
        meta["ai_statement"] = pub.ai_statement

    from apps.review.models import ReviewAssignment
    for i, a in enumerate(
            ReviewAssignment.objects.filter(
                review_round__submission=submission,
                date_completed__isnull=False).order_by("date_completed"), start=1):
        meta["reviews"].append({
            "reviewer": f"Reviewer {i}",
            "recommendation": (a.get_recommendation_display()
                               if a.recommendation else ""),
            "comments_for_author": a.comments_for_author,
            "completed": a.date_completed.isoformat(timespec="seconds")})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, sf in enumerate(submission.files.all(), start=1):
            if not sf.file:
                continue
            arc = f"files/{i:02d}-{sf.original_filename or 'file'}"
            with sf.file.open("rb") as fh:
                z.writestr(arc, fh.read())
            meta["files"].append({"path": arc,
                                  "stage": sf.get_file_stage_display(),
                                  "original_filename": sf.original_filename})
        z.writestr("package.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return buf.getvalue()


def import_package(fileobj, journal, *, submitter=None):
    """Zip paketten yeni QUEUED başvuru üretir; (submission, özet) döndürür."""
    from django.core.files.base import ContentFile
    from django.utils import timezone

    from apps.publications.models import (
        Author, Keyword, Publication, PublicationTranslation,
    )
    from .models import FileStage, Submission, SubmissionFile

    with zipfile.ZipFile(fileobj) as z:
        meta = json.loads(z.read("package.json").decode("utf-8"))
        if meta.get("package") != "ccjournal-submission":
            raise ValueError("Not a CC Journal submission package.")
        locale = meta.get("locale") or journal.primary_locale
        sub = Submission.objects.create(
            journal=journal, submitter=submitter, locale=locale,
            status=1, date_submitted=timezone.now(),
            suggested_reviewers=meta.get("suggested_reviewers") or [])
        section = journal.sections.first()
        pub = Publication.objects.create(
            submission=sub, primary_locale=locale, section=section,
            data_availability=meta.get("data_availability", ""),
            ai_statement=meta.get("ai_statement", ""))
        sub.current_publication = pub
        sub.save(update_fields=["current_publication"])
        for t in meta.get("translations") or []:
            PublicationTranslation.objects.update_or_create(
                publication=pub, locale=t.get("locale") or locale,
                defaults={"title": t.get("title", ""),
                          "subtitle": t.get("subtitle", ""),
                          "abstract": t.get("abstract", ""),
                          "body": t.get("body", "")})
        for i, a in enumerate(meta.get("authors") or []):
            Author.objects.create(
                publication=pub, seq=i,
                given_name=a.get("given_name", "") or "?",
                family_name=a.get("family_name", ""), email=a.get("email", ""),
                orcid=a.get("orcid", ""), affiliation=a.get("affiliation", ""),
                affiliation_ror=a.get("affiliation_ror", ""),
                credit_roles=a.get("credit_roles") or [])
        first = pub.authors.order_by("seq").first()
        if first:
            pub.primary_contact = first
            pub.save(update_fields=["primary_contact"])
        for i, k in enumerate(meta.get("keywords") or []):
            Keyword.objects.create(publication=pub,
                                   locale=k.get("locale") or locale,
                                   term=k.get("term", ""), seq=i)
        n_files = 0
        for entry in meta.get("files") or []:
            path = entry.get("path", "")
            if path not in z.namelist():
                continue
            data = z.read(path)
            name = entry.get("original_filename") or path.rsplit("/", 1)[-1]
            sf = SubmissionFile.objects.create(
                submission=sub, original_filename=name,
                file_stage=FileStage.SUBMISSION, file_size=len(data))
            sf.file.save(f"import/{sub.pk}-{name}", ContentFile(data), save=True)
            n_files += 1
    pub.__dict__.pop("_tr_cache", None)
    return sub, {"files": n_files, "authors": pub.authors.count(),
                 "translations": pub.translations.count()}
