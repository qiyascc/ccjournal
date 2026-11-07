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
Vitrin (reader-facing) view'ları — tek dergi.

İçerik dili (content locale) yönetimi: ?lang=xx ile değişir, oturumda saklanır,
yoksa derginin primary_locale'ine düşer. Bu, admin arayüz dilinden (İngilizce)
bağımsızdır.
"""
from __future__ import annotations

from django.http import FileResponse, Http404
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render

from apps.journals.models import Issue, Journal, Section
from apps.publications.models import Galley, Publication, PublicationStatus
from apps.submissions.models import Submission, SubmissionStatus
from apps.metadata.oai import oai_identifier


def _journal_or_404() -> Journal:
    j = Journal.current()
    if not j:
        raise Http404("No journal configured.")
    return j


def _content_locale(request, journal) -> str:
    supported = journal.supported_locales or [journal.primary_locale]
    from django.conf import settings as dj
    if getattr(dj, "LANGUAGE_URL_TYPE", "query") == "slug":
        from django.utils import translation
        active = translation.get_language() or ""
        if active in supported:
            return active
        base = active.split("-")[0]
        return base if base in supported else journal.primary_locale
    lang = request.GET.get("lang")
    if lang and lang in supported:
        request.session["content_locale"] = lang
        return lang
    return request.session.get("content_locale") or journal.primary_locale


def _base_ctx(request, journal):
    from apps.core.locales import locale_label
    cloc = _content_locale(request, journal)
    supported = journal.supported_locales or [journal.primary_locale]
    return {
        "journal": journal,
        "cloc": cloc,
        "languages": [(c, locale_label(c)) for c in supported],
        "language_links": _language_links(request, supported),
        "submit_url": _submit_url(request),
    }


def _language_links(request, supported):
    """Dil switcher hedefleri — query: ?lang=xx · slug: /xx/<yol>."""
    from django.conf import settings as dj
    from apps.core.locales import locale_label
    out = []
    if getattr(dj, "LANGUAGE_URL_TYPE", "query") == "slug":
        from apps.web.language import switch_lang_path
        for c in supported:
            out.append((c, locale_label(c), switch_lang_path(request.path, c)))
    else:
        for c in supported:
            out.append((c, locale_label(c), f"?lang={c}"))
    return out


def _submit_url(request):
    """Form Engine aktifse gönderim, form.<domain>/submission/ adresine gider."""
    try:
        from apps.configuration.services import Config
        sub = (Config.get("forms", "subdomain", "form") or "").strip().lower()
        if not sub:
            return "/submit/"
        host = request.get_host()
        bare = host.split(":")[0]
        if bare.split(".")[0] == sub:
            return "/submission/"
        return f"{request.scheme}://{sub}.{host}/submission/"
    except Exception:
        return "/submit/"


def _published_pubs():
    return Publication.objects.filter(
        status=PublicationStatus.PUBLISHED).select_related("submission", "section", "issue", "doi")


def home(request):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    current = journal.issues.filter(is_published=True, is_current=True).first() \
        or journal.issues.filter(is_published=True).first()
    ctx["current_issue"] = current
    ctx["current_pubs"] = (current.publications.filter(status=PublicationStatus.PUBLISHED)
                           .select_related("section").order_by("section__seq", "seq")) if current else []
    from constance import config
    ctx["recent"] = _published_pubs().order_by("-date_published")[:config.ITEMS_PER_PAGE]
    ctx["highlights"] = _highlights(journal, ctx["cloc"])
    from apps.journals.models import CallForPapers
    ctx["active_calls"] = list(
        CallForPapers.objects.filter(journal=journal, is_active=True)
        .order_by("seq", "-created_at")[:3])
    return render(request, "web/home.html", ctx)


def _highlights(journal, cloc):
    """Aktif highlight'lar, içerik dilinde (yoksa ilk çeviri) — karusel verisi."""
    items = []
    for h in (journal.highlights.filter(is_active=True)
              .prefetch_related("translations").order_by("seq", "id")):
        t = h.tr(cloc) or h.translations.first()
        if not t:
            continue
        items.append({"obj": h, "title": t.title, "blurb": t.blurb,
                      "cta": t.cta or "", "url": h.url or "",
                      "image": (h.image.url if h.image else "")})
    return items


def issue_galley(request, pk):
    """Tam sayı PDF'i (OJS issue galley) — paywall'a saygılı indirme."""
    journal = _journal_or_404()
    issue = get_object_or_404(Issue, pk=pk, journal=journal, is_published=True)
    if not issue.galley_file:
        raise Http404("No issue galley.")
    from apps.subscriptions.services import SubscriptionService
    if not SubscriptionService.has_access(request.user, issue):
        ctx = _base_ctx(request, journal)
        return render(request, "web/subscription_required.html", ctx, status=403)
    resp = FileResponse(issue.galley_file.open("rb"),
                        filename=f"issue-{issue.pk}.pdf")
    resp["Content-Type"] = "application/pdf"
    resp["Content-Disposition"] = f'inline; filename="issue-{issue.pk}.pdf"'
    return resp


def issue_archive(request):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    ctx["issues"] = journal.issues.filter(is_published=True)
    return render(request, "web/archive.html", ctx)


def issue_detail(request, pk):
    journal = _journal_or_404()
    issue = get_object_or_404(Issue, pk=pk, journal=journal, is_published=True)
    ctx = _base_ctx(request, journal)
    ctx["issue"] = issue
    pubs = (issue.publications.filter(status=PublicationStatus.PUBLISHED)
            .select_related("section").prefetch_related("authors").order_by("section__seq", "seq"))
    groups: dict = {}
    for p in pubs:
        groups.setdefault(p.section_id, {"section": p.section, "items": []})["items"].append(p)
    ctx["toc"] = list(groups.values())
    return render(request, "web/issue.html", ctx)


def _citation_meta(request, submission, pub, ctx):
    """Google Scholar / Highwire Press meta değerleri (şablon partial'ı doldurur)."""
    t = pub.tr(ctx["cloc"])
    j = ctx.get("journal")

    jtitle = ""
    issn = ""
    if j is not None:
        try:
            jtitle = j.tr_value("title") or ""
        except Exception:
            jtitle = ""
        issn = (getattr(j, "issn_online", "") or getattr(j, "issn_print", "") or "")

    g = pub.galleys.filter(is_approved=True, label__icontains="pdf").first()
    if g is None:
        for cand in pub.galleys.filter(is_approved=True):
            fn = (getattr(cand.file, "original_filename", "") or "").lower()
            mt = (getattr(cand.file, "mimetype", "") or "").lower()
            if fn.endswith(".pdf") or "pdf" in mt or \
                    (cand.remote_url or "").lower().endswith(".pdf"):
                g = cand
                break
    pdf_url = ""
    if g is not None:
        pdf_url = request.build_absolute_uri(
            reverse("web:galley", args=[submission.pk, g.pk]))

    issue = getattr(pub, "issue", None)
    volume = (getattr(issue, "volume", None) if issue else None) or ""
    number = (getattr(issue, "number", "") if issue else "") or ""

    firstpage = lastpage = ""
    if pub.pages:
        raw = str(pub.pages).replace("–", "-").replace("—", "-")
        parts = [p.strip() for p in raw.split("-") if p.strip()]
        if parts:
            firstpage = parts[0]
            if len(parts) > 1:
                lastpage = parts[-1]

    return {
        "journal_title": jtitle, "issn": issn,
        "volume": volume, "issue": number,
        "firstpage": firstpage, "lastpage": lastpage,
        "language": ctx["cloc"], "pdf_url": pdf_url,
        "abstract": (getattr(t, "abstract", "") if t else "") or "",
    }


def article(request, pk):
    journal = _journal_or_404()
    submission = get_object_or_404(
        Submission, pk=pk, journal=journal, status=SubmissionStatus.PUBLISHED)
    ctx = _base_ctx(request, journal)

    versions = (submission.publications.filter(status=PublicationStatus.PUBLISHED)
                .order_by("-version_major", "-version_minor"))
    pub = submission.current_publication
    vid = request.GET.get("version")
    if vid:
        pub = get_object_or_404(versions, pk=vid)
    if not pub or pub.status != PublicationStatus.PUBLISHED:
        raise Http404("Not published.")

    ctx.update({
        "submission": submission,
        "pub": pub,
        "versions": versions,
        "authors": pub.authors.all().order_by("seq"),
        "galleys": pub.galleys.filter(is_approved=True).order_by("seq"),
        "oai_id": oai_identifier(journal.path, submission.id),
        "fulltext": (pub.tr(ctx["cloc"]).body
                     if pub.tr(ctx["cloc"]) and getattr(pub.tr(ctx["cloc"]), "body", "")
                     else ""),
    })
    from apps.stats.models import Metric
    from apps.stats.services import StatsService
    StatsService.record(request, submission, Metric.ABSTRACT_VIEW)
    from constance import config as _cfg
    ctx["stats"] = StatsService.totals(submission) if _cfg.SHOW_ABSTRACT_VIEWS else None
    from apps.plugins.hooks import hooks
    ctx["plugin_html"] = hooks.apply_filters(
        "templates.article_extra", "", publication=pub, request=request)
    ctx["jsonld"] = _article_jsonld(request, submission, pub, ctx)
    ctx["scholar"] = _citation_meta(request, submission, pub, ctx)
    ctx["related"] = _related_pubs(submission, ctx["cloc"])
    vals = _monthly_spark(submission)
    ctx["spark"] = vals
    if vals:
        mx = max(vals) or 1
        ctx["spark_points"] = " ".join(
            f"{round(i * 200 / 11)},{round(32 - v * 28 / mx)}"
            for i, v in enumerate(vals))
        ctx["spark_total"] = sum(vals)
    return render(request, "web/article.html", ctx)


def _related_pubs(submission, cloc, limit: int = 4):
    """FTS benzerliğiyle "bunları da oku" — başlık kelimeleri üzerinden."""
    pub = submission.current_publication
    t = pub.tr(cloc) if pub else None
    title = (t.title if t else "") or ""
    import re as _re
    words = [w for w in _re.findall(r"\w{5,}", title)][:6]
    if not words:
        return []
    scores: dict[int, int] = {}
    try:
        from apps.search.services import SearchIndex
        for w in words:
            for rank, sid in enumerate(SearchIndex.search(w)):
                if sid == submission.pk:
                    continue
                scores[sid] = scores.get(sid, 0) + max(10 - rank, 1)
    except Exception:
        return []
    ids = [sid for sid, _ in sorted(scores.items(),
                                    key=lambda kv: -kv[1])][:limit]
    if not ids:
        return []
    pubs = {p.submission_id: p for p in _published_pubs()
            .filter(submission_id__in=ids).prefetch_related("translations", "authors")}
    return [pubs[i] for i in ids if i in pubs]


def _monthly_spark(submission, months: int = 12):
    """Son 12 ayın aylık görüntüleme toplamları (kıvılcım grafiği verisi)."""
    from datetime import date

    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    from django.utils import timezone

    from apps.stats.models import MetricDay

    today = timezone.localdate()
    y, m = today.year, today.month
    for _ in range(months - 1):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    start = date(y, m, 1)
    rows = (MetricDay.objects.filter(submission=submission, date__gte=start)
            .annotate(month=TruncMonth("date"))
            .values("month").annotate(total=Sum("count")))
    data = {(r["month"].year, r["month"].month): r["total"] for r in rows}
    out = []
    for _ in range(months):
        out.append(data.get((y, m), 0))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out if any(out) else []


def _article_jsonld(request, submission, pub, ctx):
    """schema.org ScholarlyArticle JSON-LD (Google zengin sonuçlar)."""
    import json
    t = pub.tr(ctx["cloc"])
    authors = [{"@type": "Person",
                "name": f"{a.given_name} {a.family_name}".strip(),
                **({"affiliation": a.affiliation} if a.affiliation else {}),
                **({"sameAs": f"https://orcid.org/{a.orcid}"} if a.orcid else {})}
               for a in pub.authors.all()]
    data = {
        "@context": "https://schema.org", "@type": "ScholarlyArticle",
        "headline": (t.title if t else ""),
        "abstract": (t.abstract if t else "") or "",
        "author": authors,
        "url": request.build_absolute_uri(request.path),
        "inLanguage": ctx["cloc"],
    }
    if pub.date_published:
        data["datePublished"] = pub.date_published.isoformat()
    if getattr(pub, "doi_id", None):
        data["sameAs"] = pub.doi.url
    j = ctx.get("journal")
    if j:
        jt = None
        try:
            from apps.journals.models import JournalTranslation
            row = JournalTranslation.objects.filter(journal=j).first()
            jt = row.title if row else None
        except Exception:
            pass
        data["isPartOf"] = {"@type": "Periodical", "name": jt or "Journal",
                            **({"issn": j.issn_online} if j.issn_online else {})}
    return json.dumps(data, ensure_ascii=False)


def section_browse(request, pk):
    journal = _journal_or_404()
    section = get_object_or_404(Section, pk=pk, journal=journal)
    ctx = _base_ctx(request, journal)
    ctx["section"] = section
    ctx["pubs"] = _published_pubs().filter(section=section).order_by("-date_published")
    return render(request, "web/section.html", ctx)


def search(request):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    q = (request.GET.get("q") or "").strip()
    f_year = (request.GET.get("year") or "").strip()
    f_section = (request.GET.get("section") or "").strip()
    ctx.update({"q": q, "f_year": f_year, "f_section": f_section})
    if q:
        from apps.search.services import SearchIndex
        ids = SearchIndex.search(q)
        pubs = {p.submission_id: p for p in _published_pubs()
                .filter(submission_id__in=ids)
                .prefetch_related("translations", "authors")}
        results = [pubs[i] for i in ids if i in pubs]
        ctx["facet_years"] = sorted({p.date_published.year for p in results
                                     if p.date_published}, reverse=True)
        secs = {}
        for p in results:
            if p.section_id:
                secs[p.section_id] = p.section
        ctx["facet_sections"] = [{"id": k, "title": v.tr_value("title") or f"#{k}"}
                                 for k, v in secs.items()]
        if f_year.isdigit():
            results = [p for p in results
                       if p.date_published and p.date_published.year == int(f_year)]
        if f_section.isdigit():
            results = [p for p in results if p.section_id == int(f_section)]
        ctx["results"] = results
    else:
        ctx["results"] = None
    return render(request, "web/search.html", ctx)


def keyword_browse(request, term):
    """Anahtar kelime sayfası — /keyword/<terim>/ (uzun kuyruk SEO)."""
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    pubs = (_published_pubs().filter(keywords__term__iexact=term).distinct()
            .prefetch_related("translations", "authors")
            .order_by("-date_published"))
    ctx.update({"term": term, "pubs": pubs})
    return render(request, "web/keyword.html", ctx)


def author_browse(request, pk):
    """Yazar sayfası — /author/<id>/: aynı kişinin (ORCID/ad) tüm makaleleri."""
    from apps.publications.models import Author
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    author = get_object_or_404(Author, pk=pk,
                               publication__submission__journal=journal)
    qs = _published_pubs().prefetch_related("translations", "authors")
    if author.orcid:
        pubs = qs.filter(authors__orcid=author.orcid).distinct()
    else:
        pubs = qs.filter(authors__given_name=author.given_name,
                         authors__family_name=author.family_name).distinct()
    ctx.update({"author": author, "pubs": pubs.order_by("-date_published")})
    return render(request, "web/author.html", ctx)


def accessibility(request):
    """Erişilebilirlik beyanı (EAA/WCAG) — /accessibility/."""
    journal = _journal_or_404()
    return render(request, "web/accessibility.html", _base_ctx(request, journal))


def calls_page(request):
    """Aktif çağrılar (CFP) — /calls/."""
    from apps.journals.models import CallForPapers
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    ctx["calls"] = (CallForPapers.objects
                    .filter(journal=journal, is_active=True)
                    .order_by("seq", "-created_at"))
    return render(request, "web/calls.html", ctx)


def most_cited(request):
    """Açık atıflara göre en çok atıf alan makaleler (OpenCitations verisi)."""
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    ctx["pubs"] = (_published_pubs().filter(cited_by_count__gt=0)
                   .prefetch_related("translations", "authors")
                   .order_by("-cited_by_count")[:25])
    return render(request, "web/most_cited.html", ctx)


@xframe_options_sameorigin
def galley(request, pk, galley_id):
    journal = _journal_or_404()
    submission = get_object_or_404(
        Submission, pk=pk, journal=journal, status=SubmissionStatus.PUBLISHED)
    g = get_object_or_404(Galley, pk=galley_id, publication__submission=submission, is_approved=True)
    from apps.subscriptions.services import SubscriptionService
    issue = getattr(g.publication, "issue", None)
    if not SubscriptionService.has_access(request.user, issue):
        ctx = _base_ctx(request, journal)
        ctx["submission"] = submission
        return render(request, "web/subscription_required.html", ctx, status=403)
    from apps.stats.models import Metric
    from apps.stats.services import StatsService
    StatsService.record(request, submission, Metric.GALLEY_VIEW, galley=g)
    if g.remote_url:
        return redirect(g.remote_url)
    if not g.file or not g.file.file:
        raise Http404("No file.")
    resp = FileResponse(g.file.file.open("rb"))
    if g.file.mimetype:
        resp["Content-Type"] = g.file.mimetype
    is_pdf = (g.file.mimetype or "").endswith("pdf") or \
             (g.file.original_filename or "").lower().endswith(".pdf")
    force_dl = request.GET.get("download") == "1"
    disposition = "attachment" if (force_dl or not is_pdf) else "inline"
    import unicodedata
    from urllib.parse import quote
    raw_name = g.file.original_filename or "galley.pdf"
    ascii_name = (unicodedata.normalize("NFKD", raw_name)
                  .encode("ascii", "ignore").decode("ascii")) or "galley.pdf"
    resp["Content-Disposition"] = (
        f"{disposition}; filename=\"{ascii_name}\"; "
        f"filename*=UTF-8''{quote(raw_name)}")
    resp["X-Frame-Options"] = "SAMEORIGIN"
    return resp


def setup(request):
    """Dergi yapılandırılmamışsa superuser ilk kurulumu burada yapar."""
    from django.contrib.auth.decorators import login_required as _ld  # noqa
    if Journal.current():
        return redirect("web:home")
    if not (request.user.is_authenticated and request.user.is_superuser):
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())

    from .forms import SetupForm
    from apps.journals.models import JournalTranslation
    from apps.submissions.models import Genre
    if request.method == "POST":
        form = SetupForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            journal = Journal.objects.create(
                path="journal", primary_locale=cd["primary_locale"],
                supported_locales=cd["supported_locales"],
                publisher=cd["publisher"], contact_email=cd["contact_email"],
                issn_online=cd["issn_online"], logo=cd.get("logo") or "",
                enabled=True,
            )
            JournalTranslation.objects.create(
                journal=journal, locale=cd["primary_locale"], title=cd["title"])
            from apps.journals.models import Section, SectionTranslation
            sec = Section.objects.create(journal=journal, primary_locale=cd["primary_locale"])
            SectionTranslation.objects.create(
                section=sec, locale=cd["primary_locale"], title="Articles")
            for key, name in [("article", "Article Text"), ("supp", "Supplementary")]:
                Genre.objects.get_or_create(
                    journal=journal, key=key,
                    defaults={"name": name, "is_supplementary": key == "supp"})
            return redirect("web:home")
    else:
        form = SetupForm()
    return render(request, "web/setup.html", {"form": form})


def page(request, slug):
    """Statik sayfa — içerik, içerik-diline (cloc) göre, geri-düşüşlü."""
    from apps.pages.models import StaticPage
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    pg = get_object_or_404(StaticPage, journal=journal, slug=slug, is_published=True)
    t = pg.tr(ctx["cloc"])
    if not t:
        raise Http404
    ctx.update({
        "page": pg, "ptitle": t.title, "pcontent": t.content,
        "meta_title": t.meta_title or t.title,
        "meta_description": t.meta_description,
        "canonical_url": pg.canonical_url or request.build_absolute_uri(request.path),
        "robots_noindex": pg.robots_noindex,
        "og_image": (pg.og_image.url if pg.og_image else ""),
    })
    return render(request, "web/page.html", ctx)


def announcements(request):
    """Aktif duyurular listesi (yayında + süresi geçmemiş)."""
    from django.utils import timezone
    from django.db.models import Q
    from apps.announcements.models import Announcement
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    today = timezone.localdate()
    qs = (Announcement.objects.filter(journal=journal, is_published=True)
          .filter(Q(date_expire__isnull=True) | Q(date_expire__gte=today))
          .prefetch_related("translations").order_by("-date_posted"))
    items = []
    for a in qs:
        t = a.tr(ctx["cloc"])
        if t:
            items.append({"obj": a, "title": t.title,
                          "short": t.short_description, "date": a.date_posted})
    ctx["announcements"] = items
    return render(request, "web/announcements.html", ctx)


def announcement_detail(request, pk):
    from apps.announcements.models import Announcement
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    a = get_object_or_404(Announcement, pk=pk, journal=journal, is_published=True)
    if not a.is_active:
        raise Http404
    t = a.tr(ctx["cloc"])
    if not t:
        raise Http404
    ctx.update({"ann": a, "atitle": t.title, "abody": t.body,
                "ashort": t.short_description})
    return render(request, "web/announcement_detail.html", ctx)


def reviewers_page(request):
    """Kamusal hakem teşekkür sayfası — yalnız izin veren (public_listing) hakemler."""
    from apps.review.models import ReviewerProfile
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    rows = []
    for prof in (ReviewerProfile.objects.filter(public_listing=True)
                 .select_related("user").order_by("user__family_name")):
        completed = prof.user.review_assignments.filter(
            date_completed__isnull=False).count()
        if completed:
            rows.append({"name": prof.user.full_name,
                         "affiliation": prof.affiliation, "completed": completed})
    ctx["reviewers"] = rows
    return render(request, "web/reviewers.html", ctx)


def categories(request):
    """Üst düzey kategoriler."""
    from apps.journals.models import Category
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    tops = (Category.objects.filter(journal=journal, parent__isnull=True)
            .prefetch_related("translations", "children__translations").order_by("seq"))
    ctx["categories"] = [{"obj": c, "t": c.tr(ctx["cloc"]),
                          "children": [{"obj": k, "t": k.tr(ctx["cloc"])}
                                       for k in c.children.all()]} for c in tops]
    return render(request, "web/categories.html", ctx)


def category_browse(request, slug):
    """Kategori detayı: alt kategoriler + bu kategori (ve altları) altındaki yayınlar."""
    from apps.journals.models import Category
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    cat = get_object_or_404(Category, journal=journal, slug=slug)
    ids = cat.descendant_ids()
    pubs = (_published_pubs().filter(submission__categories__in=ids).distinct()
            .select_related("section").prefetch_related("authors")
            .order_by("-date_published"))
    ctx.update({
        "category": cat, "ctitle": (cat.tr(ctx["cloc"]).title if cat.tr(ctx["cloc"]) else cat.slug),
        "cdesc": (cat.tr(ctx["cloc"]).description if cat.tr(ctx["cloc"]) else ""),
        "subcats": [{"obj": k, "t": k.tr(ctx["cloc"])} for k in cat.children.all().order_by("seq")],
        "pubs": pubs,
    })
    return render(request, "web/category.html", ctx)


AI_BOTS = ["GPTBot", "Google-Extended", "CCBot", "anthropic-ai", "ClaudeBot",
           "PerplexityBot", "Bytespider", "cohere-ai", "meta-externalagent"]


def robots_txt(request):
    from django.http import HttpResponse
    lines = ["User-agent: *", "Disallow: /admin/", "Disallow: /manage/",
             "Disallow: /rosetta/", "Disallow: /hijack/", "Disallow: /api/",
             "Allow: /"]
    try:
        from constance import config
        if config.BLOCK_AI_BOTS:
            for bot in AI_BOTS:
                lines += ["", f"User-agent: {bot}", "Disallow: /"]
    except Exception:
        pass
    lines.append(f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml")
    return HttpResponse("\n".join(lines), content_type="text/plain")


def galley_view(request, pk, galley_id):
    """HTML/PDF galley'i okuyucu kabuğu içinde gömülü gösterir (tam-metin görünümü)."""
    journal = _journal_or_404()
    submission = get_object_or_404(
        Submission, pk=pk, journal=journal, status=SubmissionStatus.PUBLISHED)
    g = get_object_or_404(Galley, pk=galley_id,
                          publication__submission=submission, is_approved=True)
    from apps.subscriptions.services import SubscriptionService
    issue = getattr(g.publication, "issue", None)
    if not SubscriptionService.has_access(request.user, issue):
        ctx = _base_ctx(request, journal)
        ctx["submission"] = submission
        return render(request, "web/subscription_required.html", ctx, status=403)
    from apps.stats.models import Metric
    from apps.stats.services import StatsService
    StatsService.record(request, submission, Metric.GALLEY_VIEW, galley=g)
    ctx = _base_ctx(request, journal)
    src = g.remote_url or reverse("web:galley", args=[submission.pk, g.pk])
    t = g.publication.tr(ctx["cloc"])
    ctx.update({"submission": submission, "pub": g.publication, "g": g,
                "src": src, "gtitle": (t.title if t else "")})
    return render(request, "web/galley_view.html", ctx)
