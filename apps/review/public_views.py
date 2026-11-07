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

"""Hakem public arayüzü — e-postadaki token linkiyle, giriş gerektirmeden.

/review/<token>/                 kabul/ret ekranı (kör hakemlik: yazar gizli)
/review/<token>/form/            değerlendirme formu (öneri + yorumlar + dosya eki)
/review/<token>/file/<id>/       hakeme açık dosyaların indirilmesi (token-kapsamlı)
/review/<token>/done/            teşekkür
"""
from django import forms
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.submissions.models import FileStage, SubmissionFile
from apps.web.views import _base_ctx, _journal_or_404

from .models import ReviewAssignment

_REVIEWER_STAGES = (FileStage.SUBMISSION, FileStage.REVIEW_FILE, FileStage.REVIEW_REVISION)


def _assignment(token):
    return get_object_or_404(
        ReviewAssignment.objects.select_related("review_round__submission"),
        access_token=token)


def _reviewer_files(sub):
    return list(sub.files.filter(file_stage__in=_REVIEWER_STAGES).order_by("file_stage", "seq"))


def _ctx(request, a):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    sub = a.review_round.submission
    pub = sub.current_publication or sub.publications.order_by("-id").first()
    t = pub.tr(ctx["cloc"]) if pub else None
    ctx.update({"a": a, "sub": sub, "pub": pub,
                "rtitle": (t.title if t else f"Submission #{sub.pk}"),
                "rabstract": (t.abstract if t else ""), "rfiles": _reviewer_files(sub)})
    return ctx


def file_download(request, token, file_id):
    """Token-kapsamlı dosya indirme: yalnız bu gönderinin hakeme açık dosyaları."""
    a = _assignment(token)
    if a.declined:
        raise Http404
    sub = a.review_round.submission
    sf = get_object_or_404(SubmissionFile, pk=file_id, submission=sub,
                           file_stage__in=_REVIEWER_STAGES)
    if not sf.file:
        raise Http404("No file.")
    resp = FileResponse(sf.file.open("rb"), as_attachment=True,
                        filename=sf.original_filename or "manuscript")
    if sf.mimetype:
        resp["Content-Type"] = sf.mimetype
    return resp


class ReviewForm(forms.Form):
    recommendation = forms.TypedChoiceField(
        coerce=int, choices=ReviewAssignment.Recommendation.choices,
        widget=forms.RadioSelect, label="Recommendation")
    comments_for_editor = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 5, "class": "field"}),
        label="Comments for the editor (confidential)")
    comments_for_author = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 5, "class": "field"}),
        label="Comments for the author")
    attachment = forms.FileField(
        required=False, label="Attachment (e.g. annotated manuscript)",
        widget=forms.ClearableFileInput(attrs={"class": "field"}))

    def __init__(self, *args, items=None, **kwargs):
        """`items`: aktif ReviewFormTemplate soruları → dinamik alanlar (rf_<id>)."""
        super().__init__(*args, **kwargs)
        self._items = list(items or [])
        for it in self._items:
            name = f"rf_{it.pk}"
            kw = {"label": it.label, "required": it.required,
                  "help_text": it.help_text}
            opts = [(c, c) for c in (it.choices or [])]
            if it.kind == it.Kind.TEXT:
                self.fields[name] = forms.CharField(
                    widget=forms.TextInput(attrs={"class": "field"}), **kw)
            elif it.kind == it.Kind.RADIO:
                self.fields[name] = forms.ChoiceField(
                    choices=opts, widget=forms.RadioSelect, **kw)
            elif it.kind == it.Kind.CHECKBOXES:
                self.fields[name] = forms.MultipleChoiceField(
                    choices=opts, widget=forms.CheckboxSelectMultiple, **kw)
            elif it.kind == it.Kind.DROPDOWN:
                self.fields[name] = forms.ChoiceField(
                    choices=[("", "—")] + opts,
                    widget=forms.Select(attrs={"class": "field"}), **kw)
            else:
                self.fields[name] = forms.CharField(
                    widget=forms.Textarea(attrs={"rows": 4, "class": "field"}), **kw)

    @property
    def custom_fields(self):
        return [self[f"rf_{it.pk}"] for it in self._items]

    def responses_snapshot(self) -> list[dict]:
        """Yanıtları şablon-bağımsız snapshot olarak döndürür."""
        out = []
        for it in self._items:
            val = self.cleaned_data.get(f"rf_{it.pk}")
            if val in (None, "", []):
                continue
            out.append({"item": it.pk, "label": it.label, "value": val})
        return out


def landing(request, token):
    a = _assignment(token)
    if a.date_completed:
        return redirect("review_public:done", token=token)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accept" and not a.declined:
            if not a.date_confirmed:
                a.date_confirmed = timezone.now()
                a.save(update_fields=["date_confirmed"])
            return redirect("review_public:form", token=token)
        if action == "decline":
            a.declined = True
            a.save(update_fields=["declined"])
            name = (request.POST.get("suggest_name") or "").strip()
            email = (request.POST.get("suggest_email") or "").strip()
            if name or email:
                sub = a.review_round.submission
                suggested = list(sub.suggested_reviewers or [])
                suggested.append({"name": name, "email": email,
                                  "reason": (request.POST.get("suggest_note") or "").strip(),
                                  "source": "declining reviewer"})
                sub.suggested_reviewers = suggested
                sub.save(update_fields=["suggested_reviewers"])
            _notify_editors(a, declined=True)
            return redirect("review_public:done", token=token)
    if a.date_confirmed and not a.declined:
        return redirect("review_public:form", token=token)
    return render(request, "review/landing.html", _ctx(request, a))


def form(request, token):
    a = _assignment(token)
    if a.declined or a.date_completed:
        return redirect("review_public:done", token=token)
    if not a.date_confirmed:
        return redirect("review_public:landing", token=token)
    from .models import ReviewFormTemplate
    tpl = ReviewFormTemplate.active_for(a.review_round.submission.journal)
    items = list(tpl.items.all()) if tpl else []
    f = ReviewForm(request.POST or None, request.FILES or None, items=items)
    if request.method == "POST" and f.is_valid():
        a.recommendation = f.cleaned_data["recommendation"]
        a.comments_for_editor = f.cleaned_data["comments_for_editor"]
        a.comments_for_author = f.cleaned_data["comments_for_author"]
        a.form_responses = f.responses_snapshot()
        a.date_completed = timezone.now()
        a.save(update_fields=["recommendation", "comments_for_editor",
                              "comments_for_author", "form_responses", "date_completed"])
        up = f.cleaned_data.get("attachment")
        if up:
            sub = a.review_round.submission
            SubmissionFile.objects.create(
                submission=sub, file=up, original_filename=up.name,
                mimetype=getattr(up, "content_type", "") or "", file_size=up.size,
                file_stage=FileStage.REVIEW_ATTACHMENT, uploader=a.reviewer)
        _notify_editors(a, declined=False)
        from .automation import on_review_completed
        try:
            on_review_completed(a)
        except Exception:
            import logging
            logging.getLogger("ccjournal.review").warning(
                "reviews-complete rule failed (assignment %s)", a.pk, exc_info=True)
        return redirect("review_public:done", token=token)
    ctx = _ctx(request, a)
    ctx["form"] = f
    ctx["review_form_tpl"] = tpl
    return render(request, "review/form.html", ctx)


def done(request, token):
    a = _assignment(token)
    return render(request, "review/done.html", _ctx(request, a))


def certificate(request, token):
    """Tamamlanmış değerlendirme için PDF sertifika (token sahibine)."""
    a = _assignment(token)
    if not a.date_completed:
        raise Http404
    from django.http import HttpResponse

    from .certificates import certificate_pdf
    resp = HttpResponse(certificate_pdf(a), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="review-certificate-{a.pk}.pdf"'
    return resp


def _notify_editors(a, *, declined):
    """Editörlere admin bildirimi (in-app)."""
    import logging
    try:
        from django.contrib.auth.models import Group
        from apps.comms.services import NotifyService
        sub = a.review_round.submission
        title = ("Reviewer declined" if declined else "Review completed")
        body = (f"{a.reviewer} {'declined' if declined else 'completed'} "
                f"the review for submission #{sub.pk}.")
        url = f"/admin/review/reviewassignment/{a.pk}/change/"
        seen = set()
        for gname in ("Editor", "Journal Manager"):
            grp = Group.objects.filter(name=gname).first()
            if not grp:
                continue
            for u in grp.user_set.filter(is_active=True):
                if u.pk in seen:
                    continue
                seen.add(u.pk)
                NotifyService.create(u, "review_done", title, body=body,
                                     journal=sub.journal, url=url)
    except Exception:
        logging.getLogger("ccjournal.review").warning(
            "editor notification failed (assignment %s)", a.pk, exc_info=True)
