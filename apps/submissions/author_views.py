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

"""Yazar iş-akışı arayüzü — token ile, giriş gerektirmeden.

Editör "revizyon iste" veya "düzelti (proof) gönder" dediğinde yazara e-postayla
gelen token linkiyle:
  /work/<token>/             durum + dosya geçmişi + (uygun aşamadaysa) yükleme
  /work/<token>/upload/      revizyon/proof dosyası yükler, ilgili aşamaya bağlar
"""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.web.views import _base_ctx, _journal_or_404

from .models import (FileStage, Stage, Submission, SubmissionFile)


def _submission(token):
    return get_object_or_404(Submission, author_token=token)


def _expected_stage(submission):
    """Yazardan hangi tür dosya bekleniyor? (stage'e göre)"""
    if submission.stage == Stage.REVIEW:
        rnd = submission.review_rounds.order_by("-round").first()
        if rnd and rnd.status == rnd.Status.REVISIONS:
            return FileStage.REVIEW_REVISION, "revision"
    if submission.stage == Stage.EDITING:
        return FileStage.COPYEDIT, "copyedit"
    if submission.stage == Stage.PRODUCTION:
        return FileStage.PROOF, "proof"
    return None, None


def _ctx(request, submission):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    pub = submission.current_publication or submission.publications.order_by("-id").first()
    t = pub.tr(ctx["cloc"]) if pub else None
    fstage, kind = _expected_stage(submission)
    files = submission.files.select_related("genre").order_by("file_stage", "seq")
    from .progress import timeline
    ctx.update({
        "submission": submission,
        "wtitle": (t.title if t else f"Submission #{submission.pk}"),
        "stage_label": submission.get_stage_display(),
        "status_label": submission.get_status_display(),
        "expected_kind": kind, "expected_stage": fstage,
        "files": files, "can_upload": fstage is not None,
        "progress": timeline(submission),
    })
    return ctx


def landing(request, token):
    submission = _submission(token)
    return render(request, "submissions/author_work.html", _ctx(request, submission))


def upload(request, token):
    submission = _submission(token)
    fstage, kind = _expected_stage(submission)
    if not fstage or request.method != "POST":
        return redirect("author_work:landing", token=token)
    f = request.FILES.get("file")
    if not f:
        messages.error(request, "Please choose a file.")
        return redirect("author_work:landing", token=token)

    sf = SubmissionFile.objects.create(
        submission=submission, file=f, original_filename=f.name,
        mimetype=getattr(f, "content_type", "") or "",
        file_size=f.size, file_stage=fstage, uploader=submission.submitter,
    )
    if kind == "revision":
        rnd = submission.review_rounds.order_by("-round").first()
        if rnd:
            rnd.status = rnd.Status.RESUBMITTED
            rnd.save(update_fields=["status"])
    _notify_editors(submission, kind, sf)
    messages.success(request, "Thank you — your file has been uploaded and the editors notified.")
    return redirect("author_work:landing", token=token)


def _notify_editors(submission, kind, sf):
    import logging
    try:
        from django.contrib.auth.models import Group
        from apps.comms.services import NotifyService
        label = {"revision": "Author uploaded a revision",
                 "copyedit": "Author returned a copyedited file",
                 "proof": "Author approved/returned a proof"}.get(kind, "Author uploaded a file")
        url = f"/admin/submissions/submission/{submission.pk}/change/"
        seen = set()
        for gname in ("Editor", "Journal Manager", "Copyeditor", "Production Editor"):
            grp = Group.objects.filter(name=gname).first()
            if not grp:
                continue
            for u in grp.user_set.filter(is_active=True):
                if u.pk in seen:
                    continue
                seen.add(u.pk)
                NotifyService.create(u, "author_upload", label,
                                     body=f"{sf.original_filename} · submission #{submission.pk}",
                                     journal=submission.journal, url=url)
    except Exception:
        logging.getLogger("ccjournal.submissions").warning(
            "editor notification failed (submission %s)", submission.pk, exc_info=True)


def package_download(request, token):
    """Kaskad paket — yalnız RET edilen gönderiler için (taşınabilir arşiv)."""
    from django.http import Http404, HttpResponse

    from .models import SubmissionStatus
    from .package import build_package

    submission = _submission(token)
    if submission.status != SubmissionStatus.DECLINED:
        raise Http404
    data = build_package(submission)
    resp = HttpResponse(data, content_type="application/zip")
    resp["Content-Disposition"] = (
        f'attachment; filename="submission-{submission.pk}-package.zip"')
    return resp


def credit_approval(request, token, atoken):
    """Ortak yazarın kendi CRediT katkısını onaylaması."""
    from django.http import Http404
    from django.utils import timezone as tz

    submission = _submission(token)
    pub = submission.current_publication
    if not pub:
        raise Http404
    author = pub.authors.filter(access_token=atoken).first()
    if author is None:
        raise Http404
    if request.method == "POST" and not author.credit_approved_at:
        author.credit_approved_at = tz.now()
        author.save(update_fields=["credit_approved_at"])
        messages.success(request, "Thank you — your contribution is confirmed.")
    ctx = _ctx(request, submission)
    from apps.publications.models import CreditRole
    labels = dict(CreditRole.choices)
    ctx.update({"author": author,
                "roles": [labels.get(r, r) for r in (author.credit_roles or [])]})
    return render(request, "submissions/author_credit.html", ctx)


def appeal(request, token):
    """Ret kararına resmi itiraz (bir kez)."""
    from .models import SubmissionStatus

    submission = _submission(token)
    if request.method != "POST" or submission.status != SubmissionStatus.DECLINED:
        return redirect("author_work:landing", token=token)
    from apps.review.models import Appeal
    if hasattr(submission, "appeal"):
        messages.error(request, "An appeal has already been filed for this submission.")
        return redirect("author_work:landing", token=token)
    reason = (request.POST.get("reason") or "").strip()
    if len(reason) < 30:
        messages.error(request, "Please explain your appeal in at least a few sentences.")
        return redirect("author_work:landing", token=token)
    Appeal.objects.create(submission=submission, reason=reason)
    try:
        from apps.review.automation import _notify_editorial
        pub = submission.current_publication
        title = (pub.tr_value("title") if pub else "") or f"Submission #{submission.pk}"
        _notify_editorial("appeal_filed", f"Appeal filed: {title}",
                          body=reason[:300],
                          url="/admin/review/appeal/", journal=submission.journal,
                          email=True)
    except Exception:
        import logging
        logging.getLogger("ccjournal.review").warning(
            "appeal notify failed (submission %s)", submission.pk, exc_info=True)
    messages.success(request, "Your appeal has been filed. The editorial team "
                              "will review it and respond by email.")
    return redirect("author_work:landing", token=token)
