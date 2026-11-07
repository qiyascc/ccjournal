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

"""Makale denetim dosyası (dossier) — /manage/dossier/<id>.pdf (editoryal).

Bir gönderinin bütün resmi geçmişi tek PDF'te: kararlar, turlar/atamalar,
dosyalar, e-posta günlüğü, entegrite özeti. COPE şikayeti, temyiz veya kurum
soruşturmasında "kanıt paketi" olarak doğrudan paylaşılabilir.
"""
from __future__ import annotations

from html import escape

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from .models import Submission

_CSS = """
@page { size: A4; margin: 1.8cm;
  @bottom-center { content: "Confidential — editorial record"; font-size: 7.5pt; color: #999; }
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 7.5pt; color: #999; } }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.5pt; color: #1c1917; }
h1 { font-size: 15pt; margin: 0 0 2px; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: .06em;
     color: #b3542e; border-bottom: 1px solid #ddd; padding-bottom: 3px; margin: 16px 0 6px; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 0.5pt solid #ccc; padding: 3.5px 6px; text-align: left; vertical-align: top; }
th { background: #f4f1ea; }
.muted { color: #78716c; }
"""


def _rows(items) -> str:
    return "".join(items)


@staff_member_required
def dossier_pdf(request, pk):
    if not (request.user.is_superuser or request.user.has_editorial_access()):
        raise Http404
    sub = get_object_or_404(
        Submission.objects.select_related("current_publication", "submitter",
                                          "journal"), pk=pk)
    from weasyprint import HTML
    pub = sub.current_publication
    t = pub.tr(pub.primary_locale) if pub else None
    title = escape((t.title if t else "") or f"Submission #{sub.pk}")

    decisions = _rows(
        f"<tr><td>{d.created_at:%Y-%m-%d %H:%M}</td>"
        f"<td>{escape(d.get_decision_display())}</td>"
        f"<td>{escape(d.editor.full_name if d.editor else '—')}</td>"
        f"<td>{escape((d.note or '')[:400])}</td></tr>"
        for d in sub.decisions.order_by("created_at")) or \
        "<tr><td colspan='4' class='muted'>No decisions recorded.</td></tr>"

    reviews = []
    for rnd in sub.review_rounds.order_by("round"):
        for a in rnd.assignments.order_by("date_assigned"):
            state = ("declined" if a.declined else
                     "completed" if a.date_completed else
                     "accepted" if a.date_confirmed else "invited")
            reviews.append(
                f"<tr><td>R{rnd.round}</td><td>{escape(a.reviewer.full_name)}</td>"
                f"<td>{state}</td>"
                f"<td>{a.date_assigned:%Y-%m-%d}</td>"
                f"<td>{a.date_due or '—'}</td>"
                f"<td>{escape(a.get_recommendation_display() if a.recommendation else '—')}</td></tr>")
    reviews_html = _rows(reviews) or \
        "<tr><td colspan='6' class='muted'>No review assignments.</td></tr>"

    files = _rows(
        f"<tr><td>{f.created_at:%Y-%m-%d}</td>"
        f"<td>{escape(f.original_filename)}</td>"
        f"<td>{escape(f.get_file_stage_display())}</td>"
        f"<td>{escape(f.uploader.full_name if f.uploader else '—')}</td></tr>"
        for f in sub.files.order_by("created_at")) or \
        "<tr><td colspan='4' class='muted'>No files.</td></tr>"

    from apps.comms.models import EmailLog
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Submission)
    emails = _rows(
        f"<tr><td>{e.created_at:%Y-%m-%d %H:%M}</td>"
        f"<td>{escape(e.to_emails[:60])}</td>"
        f"<td>{escape(e.subject[:80])}</td><td>{e.status}</td></tr>"
        for e in EmailLog.objects.filter(content_type=ct, object_id=sub.pk)
                                 .order_by("created_at")) or \
        "<tr><td colspan='4' class='muted'>No emails logged.</td></tr>"

    integ = sub.integrity_report or {}
    integ_html = (f"<p>Overall: <b>{escape(integ.get('overall', '—'))}</b> "
                  f"<span class='muted'>({escape(integ.get('generated_at', 'never run'))})"
                  f"</span></p>") if integ else "<p class='muted'>Not run.</p>"

    appeal_html = ""
    appeal = getattr(sub, "appeal", None)
    if appeal:
        appeal_html = (f"<h2>Appeal</h2><p>{appeal.created_at:%Y-%m-%d} — "
                       f"<b>{escape(appeal.get_status_display())}</b><br>"
                       f"{escape(appeal.reason[:800])}</p>")

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>{_CSS}</style></head><body>
<h1>Editorial dossier — Submission #{sub.pk}</h1>
<p class="muted">{title} · submitted {sub.date_submitted or '—'} ·
   stage {sub.get_stage_display()} · status {sub.get_status_display()} ·
   submitter {escape(sub.submitter.email if sub.submitter else '—')}</p>
<h2>Decisions</h2><table><tr><th>When</th><th>Decision</th><th>Editor</th><th>Note</th></tr>{decisions}</table>
<h2>Review assignments</h2><table><tr><th>Round</th><th>Reviewer</th><th>State</th>
<th>Assigned</th><th>Due</th><th>Recommendation</th></tr>{reviews_html}</table>
<h2>Files</h2><table><tr><th>Date</th><th>File</th><th>Stage</th><th>Uploader</th></tr>{files}</table>
<h2>Email log</h2><table><tr><th>When</th><th>To</th><th>Subject</th><th>Status</th></tr>{emails}</table>
<h2>Integrity</h2>{integ_html}
{appeal_html}
</body></html>"""
    pdf = HTML(string=html).write_pdf()
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="dossier-{sub.pk}.pdf"'
    return resp
