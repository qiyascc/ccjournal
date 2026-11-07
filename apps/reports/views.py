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

"""Editöryal raporlar — staff-only CSV indirme + indeks sayfası."""
import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render


def _csv(filename, header, rows):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    w = csv.writer(resp)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return resp


@staff_member_required
def index(request):
    reports = [
        ("Submissions", "reports:submissions"),
        ("Reviews", "reports:reviews"),
        ("Users", "reports:users"),
        ("Subscriptions", "reports:subscriptions"),
        ("Usage by month", "reports:usage_csv"),
        ("COUNTER TR_J1-like (unaudited)", "reports:counter_csv"),
        ("Editorial report (per year)", "reports:editorial_csv"),
    ]
    exports = [
        ("Crossref deposit XML", "metadata:crossref"),
        ("DOAJ articles JSON", "metadata:doaj"),
        ("PubMed ArticleSet XML", "metadata:pubmed"),
    ]
    pages = [("Usage dashboard", "reports:usage")]
    tools = []
    try:
        if request.user.is_superuser or request.user.has_editorial_access():
            from apps.review.ics import calendar_url
            tools.append(("📅 Editorial calendar (webcal — add to your phone)",
                          calendar_url(request.user)))
    except Exception:
        pass
    tools.append(("🎨 Theme colors", "/manage/theme/"))
    return render(request, "reports/index.html",
                  {"reports": reports, "exports": exports, "pages": pages,
                   "tools": tools})


def _monthly_usage(months: int = 12):
    """Son N ayın (yıl, ay, abstract, galley) toplamları — eksik aylar 0."""
    from datetime import date

    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    from apps.stats.models import Metric, MetricDay

    today = timezone.localdate()
    start = date(today.year, today.month, 1)
    y, m = start.year, start.month
    for _ in range(months - 1):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    window_start = date(y, m, 1)

    rows = (MetricDay.objects.filter(date__gte=window_start)
            .annotate(month=TruncMonth("date"))
            .values("month", "metric").annotate(total=Sum("count")))
    data: dict = {}
    for r in rows:
        key = (r["month"].year, r["month"].month)
        data.setdefault(key, {Metric.ABSTRACT_VIEW: 0, Metric.GALLEY_VIEW: 0})
        data[key][r["metric"]] = r["total"]

    out = []
    y, m = window_start.year, window_start.month
    for _ in range(months):
        vals = data.get((y, m), {})
        out.append({"year": y, "month": m,
                    "abstract": vals.get(Metric.ABSTRACT_VIEW, 0),
                    "galley": vals.get(Metric.GALLEY_VIEW, 0)})
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


@staff_member_required
def usage(request):
    """Kullanım panosu: son 12 ay bar tablosu + en çok okunan makaleler."""
    from django.db.models import Sum

    from apps.stats.models import MetricDay

    months = _monthly_usage(12)
    peak = max([r["abstract"] + r["galley"] for r in months] + [1])
    for r in months:
        r["total"] = r["abstract"] + r["galley"]
        r["pct"] = round(100 * r["total"] / peak)

    top = (MetricDay.objects.values("submission")
           .annotate(total=Sum("count")).order_by("-total")[:20])
    from apps.submissions.models import Submission
    subs = {s.pk: s for s in Submission.objects.filter(
        pk__in=[t["submission"] for t in top]).select_related("current_publication")}
    top_rows = []
    for t in top:
        s = subs.get(t["submission"])
        if not s:
            continue
        pub = s.current_publication
        top_rows.append({"id": s.pk, "total": t["total"],
                         "title": (pub.tr_value("title") if pub else "") or f"#{s.pk}"})
    return render(request, "reports/usage.html",
                  {"months": months, "top": top_rows})


@staff_member_required
def usage_csv(request):
    rows = [[f"{r['year']}-{r['month']:02d}", r["abstract"], r["galley"],
             r["abstract"] + r["galley"]] for r in _monthly_usage(24)]
    return _csv("usage-monthly.csv",
                ["Month", "Abstract views", "Galley views/downloads", "Total"], rows)


@staff_member_required
def counter_csv(request):
    """COUNTER 5 TR_J1-benzeri aylık rapor (denetimsiz — başlıkta açıkça yazar).

    Total_Item_Investigations = özet + galley görüntüleme;
    Total_Item_Requests = galley görüntüleme/indirme. Unique_* metrikleri
    oturum-bazlı sayım gerektirir; günlük agregede tutulmadığından rapor dışıdır.
    """
    from django.utils import timezone

    from apps.journals.models import Journal

    j = Journal.current()
    jt = j.tr() if j else None
    months = _monthly_usage(12)
    labels = [f"{r['year']}-{r['month']:02d}" for r in months]

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="counter-tr-j1.csv"'
    w = csv.writer(resp)
    w.writerow(["Report_Name", "Journal Requests (TR_J1-like, unaudited)"])
    w.writerow(["Report_ID", "TR_J1"])
    w.writerow(["Release", "5-like (not COUNTER audited)"])
    w.writerow(["Institution_Name", "All"])
    w.writerow(["Metric_Types", "Total_Item_Investigations; Total_Item_Requests"])
    w.writerow(["Reporting_Period", f"{labels[0]} to {labels[-1]}"])
    w.writerow(["Created", timezone.now().isoformat(timespec="seconds")])
    w.writerow(["Created_By", "CC Journal"])
    w.writerow([])
    w.writerow(["Title", "Publisher", "ISSN", "Metric_Type",
                "Reporting_Period_Total", *labels])
    title = (jt.title if jt else "Journal")
    publisher = (j.publisher if j else "")
    issn = (j.issn_online or j.issn_print) if j else ""
    inv = [r["abstract"] + r["galley"] for r in months]
    req = [r["galley"] for r in months]
    w.writerow([title, publisher, issn, "Total_Item_Investigations", sum(inv), *inv])
    w.writerow([title, publisher, issn, "Total_Item_Requests", sum(req), *req])
    return resp


@staff_member_required
def editorial_csv(request):
    """Yıllık editoryal rapor: gelen, kabul, red, kabul oranı (OJS Editorial Report)."""
    from collections import defaultdict

    from apps.review.models import EditorialDecision
    from apps.submissions.models import Submission

    D = EditorialDecision.Decision
    received = defaultdict(int)
    for s in Submission.objects.exclude(date_submitted=None):
        received[s.date_submitted.year] += 1
    accepted = defaultdict(int)
    declined = defaultdict(int)
    seen: set = set()
    for d in (EditorialDecision.objects
              .filter(decision__in=[D.ACCEPT, D.DECLINE, D.INITIAL_DECLINE])
              .order_by("created_at")):
        if d.submission_id in seen:
            continue
        seen.add(d.submission_id)
        if d.decision == D.ACCEPT:
            accepted[d.created_at.year] += 1
        else:
            declined[d.created_at.year] += 1
    years = sorted(set(received) | set(accepted) | set(declined))
    rows = []
    for y in years:
        a, r = accepted[y], declined[y]
        rate = f"{100 * a / (a + r):.0f}%" if (a + r) else ""
        rows.append([y, received[y], a, r, rate])
    return _csv("editorial-report.csv",
                ["Year", "Submissions received", "Accepted", "Declined",
                 "Acceptance rate"], rows)


@staff_member_required
def submissions_csv(request):
    from apps.submissions.models import Submission
    rows = []
    for s in (Submission.objects.select_related("submitter", "current_publication__section")
              .prefetch_related("current_publication__translations").order_by("id")):
        pub = s.current_publication
        t = pub.tr() if pub else None
        rows.append([
            s.id, (t.title if t else ""), (str(pub.section) if pub and pub.section_id else ""),
            s.get_stage_display() if hasattr(s, "get_stage_display") else s.stage,
            s.get_status_display() if hasattr(s, "get_status_display") else s.status,
            (s.submitter.email if s.submitter_id else ""),
            (s.date_submitted.isoformat() if s.date_submitted else ""),
        ])
    return _csv("submissions.csv",
                ["ID", "Title", "Section", "Stage", "Status", "Submitter", "Submitted"], rows)


@staff_member_required
def reviews_csv(request):
    from apps.review.models import ReviewAssignment
    rows = []
    for a in (ReviewAssignment.objects.select_related("reviewer", "review_round__submission")
              .order_by("id")):
        days = ((a.date_completed - a.date_assigned).days
                if a.date_completed and a.date_assigned else "")
        rows.append([
            a.review_round.submission_id, (a.reviewer.email if a.reviewer_id else ""),
            a.date_assigned.isoformat() if a.date_assigned else "",
            a.date_completed.isoformat() if a.date_completed else "",
            a.get_recommendation_display() if a.recommendation else "",
            "yes" if a.declined else "no", days, a.quality or "",
        ])
    return _csv("reviews.csv",
                ["Submission", "Reviewer", "Assigned", "Completed", "Recommendation",
                 "Declined", "Days", "Quality"], rows)


@staff_member_required
def users_csv(request):
    from apps.accounts.models import User
    rows = []
    for u in User.objects.prefetch_related("groups").order_by("id"):
        roles = ", ".join(g.name for g in u.groups.all())
        rows.append([u.email, (u.given_name + " " + u.family_name).strip(),
                     str(u.country) if u.country else "", roles,
                     u.created_at.date().isoformat() if u.created_at else ""])
    return _csv("users.csv", ["Email", "Name", "Country", "Roles", "Joined"], rows)


@staff_member_required
def subscriptions_csv(request):
    from apps.subscriptions.models import Subscription
    rows = []
    for s in Subscription.objects.select_related("user", "type").order_by("id"):
        rows.append([
            (s.user.email if s.user_id else s.institution_name), s.type.name,
            s.get_status_display(), s.date_start.isoformat(), s.date_end.isoformat(),
            "yes" if s.is_current else "no",
        ])
    return _csv("subscriptions.csv",
                ["Subscriber", "Type", "Status", "Start", "End", "Current"], rows)
