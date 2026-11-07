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
Gönderi sihirbazı (server-render + Alpine.js). Adımlar:
start → files → metadata → authors → confirm → done.

İş kuralları yine servis katmanında; bu view'lar yalnızca form/akış yönetir.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.journals.models import Journal
from apps.publications.models import Author, Keyword, Publication, PublicationTranslation
from .forms import MetadataForm, StartForm
from .models import (
    FileStage, Genre, Stage, Submission, SubmissionFile, SubmissionStatus,
)

STEPS = ["start", "files", "metadata", "authors", "confirm"]


@login_required
def quick(request):
    """Format-free tek dosya başvurusu: "önce bilim, biçimi biz hallederiz".

    Yazar TEK dosya yükler; .docx ise başlık ve tam metin otomatik çıkarılır
    (ilk başlık satırı → title; kalanı body), değilse dosya adı başlık olur.
    Metadata'yı sonradan yazar (/work/) veya editör tamamlar. Araştırma: dergi
    biçimine uydurmak makale başına ~14 saat; bu akış onu sıfırlar.
    """
    journal = Journal.current()
    error = ""
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f:
            error = "Please choose your manuscript file."
        elif not request.POST.get("agree"):
            error = "Please confirm the submission is your own original work."
        else:
            section = (journal.sections.filter(is_editor_restricted=False).first()
                       or journal.sections.first())
            locale = request.POST.get("locale") or journal.primary_locale
            supported = journal.supported_locales or [journal.primary_locale]
            if locale not in supported:
                locale = journal.primary_locale
            sub = Submission.objects.create(
                journal=journal, submitter=request.user, locale=locale,
                stage=Stage.SUBMISSION, status=SubmissionStatus.QUEUED,
                date_submitted=timezone.now())
            pub = Publication.objects.create(
                submission=sub, primary_locale=locale, section=section)
            sub.current_publication = pub
            sub.save(update_fields=["current_publication"])
            genre = Genre.objects.filter(journal=journal).first()
            SubmissionFile.objects.create(
                submission=sub, file=f, original_filename=f.name,
                mimetype=getattr(f, "content_type", "") or "", file_size=f.size,
                file_stage=FileStage.SUBMISSION, genre=genre, uploader=request.user)
            title = _quick_extract(pub, f.name, locale)
            u = request.user
            Author.objects.create(
                publication=pub, given_name=u.given_name, family_name=u.family_name,
                email=u.email, orcid=u.orcid, affiliation=u.affiliation, seq=0)
            pub.primary_contact = pub.authors.first()
            pub.save(update_fields=["primary_contact"])
            from apps.comms.services import submission_created
            submission_created.send(sender=Submission, submission=sub)
            from apps.plugins.hooks import hooks
            hooks.do_action("submission.submitted", submission=sub)
            return render(request, "wizard/quick_done.html",
                          {"submission": sub, "title": title})
    supported = (journal.supported_locales or [journal.primary_locale]) if journal else []
    from apps.core.locales import locale_label
    return render(request, "wizard/quick.html", {
        "journal": journal, "error": error,
        "locales": [(c, locale_label(c)) for c in supported],
    })


def _quick_extract(pub, filename: str, locale: str) -> str:
    """.docx'ten başlık+gövde çıkarır; olmazsa dosya adından başlık üretir."""
    import re

    from apps.publications.docx_import import import_body_from_manuscript

    title = ""
    t, _warnings = import_body_from_manuscript(pub, locale=locale, overwrite=True)
    if t and t.body:
        m = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", t.body, re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            t.body = t.body.replace(m.group(0), "", 1)
    if not title:
        stem = filename.rsplit(".", 1)[0]
        title = re.sub(r"[_\-]+", " ", stem).strip().capitalize() or "Untitled"
    if t is None:
        t = PublicationTranslation.objects.create(publication=pub, locale=locale)
    t.title = title[:512]
    t.save()
    return title


def _owned(request, pk) -> Submission:
    sub = get_object_or_404(Submission, pk=pk)
    if sub.submitter_id != request.user.id and not request.user.is_staff:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    return sub


def _ctx(sub: Submission, step: str, **extra):
    return {"submission": sub, "steps": STEPS, "current_step": step,
            "step_index": STEPS.index(step), **extra}


@login_required
def start(request):
    journal = Journal.current()
    if request.method == "POST":
        form = StartForm(request.POST, journal=journal, locale=getattr(request, "content_locale", None))
        if form.is_valid():
            sub = Submission.objects.create(
                journal=journal, submitter=request.user,
                locale=form.cleaned_data["locale"],
                stage=Stage.SUBMISSION, status=SubmissionStatus.INCOMPLETE,
            )
            pub = Publication.objects.create(
                submission=sub, primary_locale=sub.locale,
                section=form.cleaned_data["section"],
            )
            sub.current_publication = pub
            sub.save(update_fields=["current_publication"])
            return redirect("submit:files", pk=sub.pk)
    else:
        form = StartForm(journal=journal, locale=getattr(request, "content_locale", None))
    guidelines = ""
    if journal:
        t = journal.tr()
        guidelines = getattr(t, "author_guidelines", "") if t else ""
    return render(request, "wizard/start.html",
                  {"form": form, "steps": STEPS, "current_step": "start", "step_index": 0,
                   "journal": journal, "guidelines": guidelines})


@login_required
def files(request, pk):
    sub = _owned(request, pk)
    if request.method == "POST":
        if request.FILES.get("file"):
            f = request.FILES["file"]
            genre = Genre.objects.filter(journal=sub.journal).first()
            SubmissionFile.objects.create(
                submission=sub, file=f, original_filename=f.name,
                mimetype=getattr(f, "content_type", ""), file_size=f.size,
                file_stage=FileStage.SUBMISSION, genre=genre, uploader=request.user,
            )
            return redirect("submit:files", pk=sub.pk)
        return redirect("submit:metadata", pk=sub.pk)
    return render(request, "wizard/files.html",
                  _ctx(sub, "files", files=sub.files.filter(file_stage=FileStage.SUBMISSION)))


@login_required
def metadata(request, pk):
    sub = _owned(request, pk)
    pub = sub.current_publication
    tr = pub.translations.filter(locale=pub.primary_locale).first()
    if request.method == "POST":
        form = MetadataForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            PublicationTranslation.objects.update_or_create(
                publication=pub, locale=pub.primary_locale,
                defaults={"title": cd["title"], "subtitle": cd["subtitle"],
                          "abstract": cd["abstract"]},
            )
            pub.keywords.filter(locale=pub.primary_locale).delete()
            terms = [t.strip() for t in cd["keywords"].split(",") if t.strip()]
            Keyword.objects.bulk_create([
                Keyword(publication=pub, locale=pub.primary_locale, term=t, seq=i)
                for i, t in enumerate(terms)
            ])
            return redirect("submit:authors", pk=sub.pk)
    else:
        initial = {}
        if tr:
            initial = {"title": tr.title, "subtitle": tr.subtitle, "abstract": tr.abstract}
        initial["keywords"] = ", ".join(
            pub.keywords.filter(locale=pub.primary_locale).values_list("term", flat=True))
        form = MetadataForm(initial=initial)
    return render(request, "wizard/metadata.html", _ctx(sub, "metadata", form=form))


@login_required
def authors(request, pk):
    sub = _owned(request, pk)
    pub = sub.current_publication
    if request.method == "POST":
        given = request.POST.getlist("given_name")
        family = request.POST.getlist("family_name")
        email = request.POST.getlist("email")
        orcid = request.POST.getlist("orcid")
        affil = request.POST.getlist("affiliation")
        rors = request.POST.getlist("affiliation_ror")
        pub.authors.all().delete()
        rows = []
        for i, g in enumerate(given):
            if not g.strip():
                continue
            rows.append(Author(
                publication=pub, given_name=g.strip(),
                family_name=family[i].strip() if i < len(family) else "",
                email=email[i].strip() if i < len(email) else "",
                orcid=orcid[i].strip() if i < len(orcid) else "",
                affiliation=affil[i].strip() if i < len(affil) else "",
                affiliation_ror=rors[i].strip() if i < len(rors) else "",
                seq=i,
            ))
        for r in rows:
            r.save()
        if rows:
            pub.primary_contact = pub.authors.order_by("seq").first()
            pub.save(update_fields=["primary_contact"])
        return redirect("submit:confirm", pk=sub.pk)

    existing = list(pub.authors.order_by("seq").values(
        "given_name", "family_name", "email", "orcid", "affiliation",
        "affiliation_ror"))
    if not existing:
        u = request.user
        existing = [{"given_name": u.given_name, "family_name": u.family_name,
                     "email": u.email, "orcid": u.orcid,
                     "affiliation": u.affiliation,
                     "affiliation_ror": u.affiliation_ror}]
    return render(request, "wizard/authors.html", _ctx(sub, "authors", authors_json=existing))


@login_required
def confirm(request, pk):
    sub = _owned(request, pk)
    pub = sub.current_publication
    if request.method == "POST":
        names = request.POST.getlist("sr_name")
        emails = request.POST.getlist("sr_email")
        reasons = request.POST.getlist("sr_reason")
        suggested = []
        for i, name in enumerate(names):
            name = (name or "").strip()
            email = (emails[i] if i < len(emails) else "").strip()
            if not (name or email):
                continue
            suggested.append({"name": name, "email": email,
                              "reason": (reasons[i] if i < len(reasons) else "").strip()})
        sub.suggested_reviewers = suggested
        pub.data_availability = (request.POST.get("data_availability") or "").strip()
        pub.ai_statement = (request.POST.get("ai_statement") or "").strip()
        lic = (request.POST.get("license") or "").strip()
        if lic:
            pub.license_url = "" if lic == "none" else lic
        pub.save(update_fields=["data_availability", "ai_statement", "license_url"])
        sub.status = SubmissionStatus.QUEUED
        sub.date_submitted = timezone.now()
        sub.save(update_fields=["suggested_reviewers", "status", "date_submitted",
                                "date_status_modified"])
        from apps.comms.services import submission_created
        submission_created.send(sender=Submission, submission=sub)
        from apps.plugins.hooks import hooks
        hooks.do_action("submission.submitted", submission=sub)
        return redirect("submit:done", pk=sub.pk)
    return render(request, "wizard/confirm.html",
                  _ctx(sub, "confirm", pub=pub, tr=pub.tr(pub.primary_locale),
                       authors=pub.authors.order_by("seq"),
                       files=sub.files.filter(file_stage=FileStage.SUBMISSION)))


@login_required
def done(request, pk):
    sub = _owned(request, pk)
    return render(request, "wizard/done.html", {"submission": sub})
