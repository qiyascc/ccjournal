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
Dosya yöneticisi — /manage/files/<submission_id>/ (staff).

OJS'in aşama-bazlı dosya panellerinin karşılığı: bir gönderinin dosyaları
aşama kolonlarında (Submission → Review → Revisions → Copyediting → Proof →
Production-ready) gruplanır; buradan aşamaya dosya yüklenir ve bir dosya
"sonraki aşamaya kopyala" ile taşınır (source_file zinciri korunur, içerik
FİZİKSEL olarak kopyalanır — django_cleanup paylaşılan dosyayı silemesin).
İndirme public /media yerine staff-korumalı endpoint üzerinden yapılır.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import FileStage, Submission, SubmissionFile

STAGES = [
    (FileStage.SUBMISSION, "Submission"),
    (FileStage.REVIEW_FILE, "Sent to review"),
    (FileStage.REVIEW_ATTACHMENT, "Reviewer attachments"),
    (FileStage.REVIEW_REVISION, "Author revisions"),
    (FileStage.COPYEDIT, "Copyediting"),
    (FileStage.PROOF, "Proofs"),
    (FileStage.PRODUCTION_READY, "Production-ready"),
]
_STAGE_VALUES = {s for s, _ in STAGES}

PROMOTE_TO = {
    FileStage.SUBMISSION: FileStage.REVIEW_FILE,
    FileStage.REVIEW_FILE: FileStage.COPYEDIT,
    FileStage.REVIEW_REVISION: FileStage.COPYEDIT,
    FileStage.COPYEDIT: FileStage.PROOF,
    FileStage.PROOF: FileStage.PRODUCTION_READY,
}

_PRODUCTION_ROLES = {"Copyeditor", "Layout Editor", "Proofreader", "Journal Assistant"}


def _can(user) -> bool:
    if not (getattr(user, "is_authenticated", False) and user.is_staff):
        return False
    return (user.is_superuser or user.has_editorial_access()
            or bool(user.role_names & _PRODUCTION_ROLES))


@staff_member_required
def manage_files(request, pk):
    if not _can(request.user):
        raise Http404
    sub = get_object_or_404(
        Submission.objects.select_related("current_publication"), pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "upload":
            f = request.FILES.get("file")
            try:
                stage = int(request.POST.get("stage", ""))
            except (TypeError, ValueError):
                stage = 0
            if f and stage in _STAGE_VALUES:
                SubmissionFile.objects.create(
                    submission=sub, file=f, original_filename=f.name,
                    mimetype=getattr(f, "content_type", "") or "",
                    file_size=f.size, file_stage=stage, uploader=request.user)
                messages.success(request, f"Uploaded “{f.name}”.")
            else:
                messages.error(request, "Choose a file and a valid stage.")
        elif action == "promote":
            sf = get_object_or_404(SubmissionFile, pk=request.POST.get("file_id"),
                                   submission=sub)
            target = PROMOTE_TO.get(sf.file_stage)
            if target is None:
                messages.error(request, "This file has no next stage.")
            else:
                new = SubmissionFile(
                    submission=sub, original_filename=sf.original_filename,
                    mimetype=sf.mimetype, file_size=sf.file_size,
                    file_stage=target, genre=sf.genre, uploader=request.user,
                    source_file=sf)
                with sf.file.open("rb") as fh:
                    new.file.save(sf.original_filename, ContentFile(fh.read()),
                                  save=False)
                new.save()
                messages.success(
                    request,
                    f"“{sf.original_filename}” copied to "
                    f"{FileStage(target).label}.")
        elif action == "make_galley":
            sf = get_object_or_404(SubmissionFile, pk=request.POST.get("file_id"),
                                   submission=sub)
            pub = sub.current_publication
            if not pub:
                messages.error(request, "No current publication to attach a galley to.")
            else:
                from apps.publications.models import Galley
                ext = (sf.original_filename.rsplit(".", 1)[-1] if "." in sf.original_filename
                       else "").lower()
                label = {"pdf": "PDF", "html": "HTML", "htm": "HTML",
                         "xml": "XML", "epub": "EPUB"}.get(ext, ext.upper() or "FILE")
                Galley.objects.create(
                    publication=pub, label=label, file=sf, is_approved=True,
                    seq=(pub.galleys.count() + 1) * 1.0)
                messages.success(
                    request,
                    f"Galley “{label}” created from “{sf.original_filename}” "
                    "(approved). It appears on the article once published.")
        return redirect("manage_files", pk=sub.pk)

    files = list(sub.files.select_related("genre", "uploader", "source_file")
                 .order_by("file_stage", "seq", "created_at"))
    by_stage = {s: [] for s, _ in STAGES}
    other = []
    for f in files:
        if f.file_stage in by_stage:
            by_stage[f.file_stage].append(f)
        else:
            other.append(f)
    columns = [{"stage": s, "label": label, "files": by_stage[s],
                "next": PROMOTE_TO.get(s)}
               for s, label in STAGES]
    pub = sub.current_publication
    title = (pub.tr_value("title") if pub else "") or f"Submission #{sub.pk}"
    return render(request, "manage/files.html", {
        "sub": sub, "stitle": title, "columns": columns, "other": other,
        "stages": STAGES,
    })


@staff_member_required
def download_file(request, pk, file_id):
    """Staff-korumalı dosya indirme (public /media yoluna bağımlı değil)."""
    if not _can(request.user):
        raise Http404
    sf = get_object_or_404(SubmissionFile, pk=file_id, submission_id=pk)
    if not sf.file:
        raise Http404("No file.")
    resp = FileResponse(sf.file.open("rb"), as_attachment=True,
                        filename=sf.original_filename or "file")
    if sf.mimetype:
        resp["Content-Type"] = sf.mimetype
    return resp
