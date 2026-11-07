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

"""Hakem sertifikaları — tanınırlık, sürdürülebilir teşviklerin en ucuzu.

Tamamlanan her değerlendirme için indirilebilir PDF sertifika üretir
(kör hakemliği korumak için makale başlığı YAZILMAZ, gönderi numarası yeter).
Terfi/atama dosyasına konabilir; yıl sonu özeti e-postasıyla tamamlanır.
"""
from __future__ import annotations

_CERT_HTML = """\
<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4 landscape; margin: 1.6cm; }}
body {{ font-family: 'DejaVu Serif', Georgia, serif; color: #1c1917;
       display: flex; align-items: center; justify-content: center; height: 100%; }}
.frame {{ border: 3px double #8a6d3b; padding: 2.2cm 2.8cm; text-align: center;
          width: 100%; }}
.journal {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10pt;
           letter-spacing: .22em; text-transform: uppercase; color: #8a6d3b; }}
h1 {{ font-size: 26pt; margin: .55cm 0 .2cm; font-weight: normal; }}
.name {{ font-size: 20pt; margin: .5cm 0 .15cm; font-style: italic; }}
.text {{ font-size: 11pt; line-height: 1.6; color: #44403c; max-width: 17cm;
        margin: 0 auto; }}
.meta {{ margin-top: .9cm; font-family: 'DejaVu Sans', Arial, sans-serif;
        font-size: 8.5pt; color: #78716c; letter-spacing: .06em; }}
.rule {{ width: 4cm; border: none; border-top: 1px solid #8a6d3b; margin: .8cm auto .15cm; }}
.sign {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9pt; color: #57534e; }}
</style></head><body>
<div class="frame">
  <div class="journal">{journal}</div>
  <h1>Certificate of Peer Review</h1>
  <div class="text">This certifies that</div>
  <div class="name">{reviewer}</div>
  <div class="text">completed an expert peer review for <b>{journal}</b>
    on {date}.<br>The journal gratefully acknowledges this contribution
    to scholarly quality.</div>
  <hr class="rule">
  <div class="sign">Editorial Office</div>
  <div class="meta">Review reference: SUB-{sub_id} · Certificate ID: RC-{cert_id}</div>
</div>
</body></html>
"""


def certificate_pdf(assignment) -> bytes:
    """Tamamlanmış atama için PDF sertifika byte'ları."""
    from weasyprint import HTML

    sub = assignment.review_round.submission
    journal = sub.journal
    jt = journal.tr()
    html = _CERT_HTML.format(
        journal=(jt.title if jt else journal.path),
        reviewer=assignment.reviewer.full_name or assignment.reviewer.email,
        date=assignment.date_completed.strftime("%d %B %Y"),
        sub_id=sub.pk, cert_id=assignment.pk,
    )
    return HTML(string=html).write_pdf()


def year_stats(user, year: int) -> dict | None:
    """Bir hakemin yıllık özeti; o yıl tamamlanmış işi yoksa None."""
    from .models import ReviewAssignment

    done = list(ReviewAssignment.objects.filter(
        reviewer=user, date_completed__year=year))
    if not done:
        return None
    days = [(a.date_completed - a.date_assigned).days
            for a in done if a.date_assigned]
    on_time = sum(1 for a in done
                  if not a.date_due or a.date_completed.date() <= a.date_due)
    return {"year": year, "completed": len(done),
            "avg_days": round(sum(days) / len(days), 1) if days else None,
            "on_time": on_time}


def send_year_summary(user, year: int) -> bool:
    """Yıl özeti e-postası (İngilizce, raw kanal dağıtımıyla)."""
    from apps.comms.services import NotificationService
    from apps.journals.models import Journal

    stats = year_stats(user, year)
    if not stats or not user.email:
        return False
    journal = Journal.current()
    jt = journal.tr() if journal else None
    jname = (jt.title if jt else "the journal")
    subject = f"Thank you for reviewing in {year} — {jname}"
    body = (f"Dear {user.full_name or 'reviewer'},\n\n"
            f"In {year} you completed {stats['completed']} peer review(s) for "
            f"{jname}"
            + (f", averaging {stats['avg_days']} days per review"
               if stats['avg_days'] is not None else "")
            + f" ({stats['on_time']} on time).\n\n"
            "Your certificates are available from each review's completion page, "
            "and this record can be cited in promotion and tenure files.\n\n"
            "With sincere thanks,\nThe Editorial Office")
    results = NotificationService.notify_raw(
        journal=journal, to=[user.email], subject=subject, body=body,
        key="reviewer_year_summary", related=user)
    return any(ok for ok, _ in results.values())
