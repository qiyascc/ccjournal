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

"""Entegrite kontrolleri — küçük derginin ücretsiz iThenticate'i.

Paper-mill/özensizlik sinyallerini ÜCRETSİZ kaynaklarla üretir; karar vermez,
editöre işaret listesi sunar (insan karar verir):

  * references  — kaynakçadaki DOI'ler Crossref'te var mı? (uydurma referans)
  * retracted   — kaynaklardan geri çekilmiş olan var mı? (Crossref update-to)
  * similarity  — derginin KENDİ arşivine karşı başlık/özet benzerliği (FTS5)
  * emails      — tek kullanımlık e-posta alan adları
  * self_citation — kaynakçada yazar soyadlarının oranı (aşırı öz-atıf)
  * orcid       — ORCID'siz yazar oranı (bilgi düzeyi)

Ağ gerektiren kontroller (Crossref) yalnız `network=True` ile koşar; otomatik
tetikleyici eager modda yalnız yerel kontrolleri çalıştırır, tam tarama admin
panelindeki düğmeden/worker'dan yapılır.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone

logger = logging.getLogger("ccjournal.integrity")

CROSSREF_WORKS = "https://api.crossref.org/works/{doi}"
MAX_DOI_LOOKUPS = 20

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "yopmail.com",
    "tempmail.com", "temp-mail.org", "sharklasers.com", "trashmail.com",
    "getnada.com", "dispostable.com", "maildrop.cc", "fakeinbox.com",
}

SELF_CITE_WARN_RATIO = 0.4
SELF_CITE_MIN_REFS = 5


def _crossref_fetch(doi: str) -> dict | None:
    """Crossref work kaydı; 404 → None. Testlerde monkeypatch edilir."""
    url = CROSSREF_WORKS.format(doi=urllib.parse.quote(doi, safe=""))
    req = urllib.request.Request(url, headers={
        "User-Agent": "ccjournal-integrity (mailto:admin@example.org)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("message")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _check_references(pub, *, network: bool) -> dict:
    cites = list(pub.citations.all()) if pub else []
    with_doi = [c for c in cites if (c.doi or "").strip()]
    if not network:
        return {"status": "info", "total": len(cites), "with_doi": len(with_doi),
                "detail": "Network checks not run yet — use “Run full checks”."}
    bad, retracted = [], []
    for c in with_doi[:MAX_DOI_LOOKUPS]:
        doi = c.doi.strip().replace("https://doi.org/", "")
        try:
            work = _crossref_fetch(doi)
        except Exception:
            logger.warning("crossref lookup failed for %s", doi, exc_info=True)
            continue
        if work is None:
            bad.append(doi)
            continue
        for upd in (work.get("update-to") or []):
            if "retract" in (upd.get("type") or "").lower():
                retracted.append(doi)
    status = "ok"
    if bad:
        status = "warn"
    if retracted:
        status = "alert"
    return {"status": status, "total": len(cites), "with_doi": len(with_doi),
            "checked": min(len(with_doi), MAX_DOI_LOOKUPS),
            "unresolved": bad, "retracted": retracted,
            "detail": (f"{len(bad)} DOI(s) do not resolve on Crossref; " if bad else "")
                      + (f"{len(retracted)} cited work(s) RETRACTED" if retracted else "")
                      or "All checked DOIs resolve."}


def _check_similarity(submission, pub) -> dict:
    """Kendi arşivine karşı kaba benzerlik: başlık kelimeleriyle FTS araması."""
    t = pub.tr(pub.primary_locale) if pub else None
    title = (t.title if t else "") or ""
    if len(title.split()) < 3:
        return {"status": "info", "detail": "Title too short for a similarity probe.",
                "matches": []}
    try:
        from apps.search.services import SearchIndex
        ids = [i for i in SearchIndex.search(title) if i != submission.pk][:3]
    except Exception:
        return {"status": "info", "detail": "Search index unavailable.", "matches": []}
    matches = []
    if ids:
        from apps.publications.models import Publication, PublicationStatus
        for p in (Publication.objects
                  .filter(submission_id__in=ids, status=PublicationStatus.PUBLISHED)
                  .prefetch_related("translations")):
            pt = p.tr(p.primary_locale)
            if not pt:
                continue
            overlap = _word_overlap(title, pt.title)
            if overlap >= 0.6:
                matches.append({"submission": p.submission_id,
                                "title": pt.title, "overlap": round(overlap, 2)})
    return {"status": "warn" if matches else "ok",
            "matches": matches,
            "detail": (f"{len(matches)} archive item(s) with ≥60% title overlap"
                       if matches else "No close matches in this journal's archive.")}


def _word_overlap(a: str, b: str) -> float:
    wa = {w for w in re.findall(r"\w{4,}", a.lower())}
    wb = {w for w in re.findall(r"\w{4,}", b.lower())}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _check_emails(submission, pub) -> dict:
    emails = [submission.submitter.email] if submission.submitter else []
    if pub:
        emails += [a.email for a in pub.authors.all() if a.email]
    flagged = sorted({e for e in emails
                      if e.rsplit("@", 1)[-1].lower() in DISPOSABLE_DOMAINS})
    return {"status": "warn" if flagged else "ok", "flagged": flagged,
            "detail": (f"Disposable email domain(s): {', '.join(flagged)}"
                       if flagged else "No disposable email domains.")}


def _check_self_citation(pub) -> dict:
    if not pub:
        return {"status": "info", "detail": "No publication.", "ratio": 0}
    cites = list(pub.citations.all())
    surnames = [a.family_name for a in pub.authors.all() if len(a.family_name or "") > 3]
    if len(cites) < SELF_CITE_MIN_REFS or not surnames:
        return {"status": "info", "ratio": 0,
                "detail": "Too few references/authors for a self-citation signal."}
    hits = sum(1 for c in cites
               if any(s.lower() in (c.raw or "").lower() for s in surnames))
    ratio = hits / len(cites)
    return {"status": "warn" if ratio > SELF_CITE_WARN_RATIO else "ok",
            "ratio": round(ratio, 2), "hits": hits, "total": len(cites),
            "detail": f"{hits}/{len(cites)} references mention an author surname."}


def _check_orcid(pub) -> dict:
    if not pub:
        return {"status": "info", "detail": "No publication.", "share": 0}
    authors = list(pub.authors.all())
    if not authors:
        return {"status": "info", "detail": "No authors.", "share": 0}
    without = sum(1 for a in authors if not a.orcid)
    share = without / len(authors)
    return {"status": "info", "share": round(share, 2),
            "detail": f"{without}/{len(authors)} author(s) without ORCID."}


def run_checks(submission, *, network: bool = True) -> dict:
    """Raporu üretir, submission'a kaydeder ve döndürür."""
    pub = submission.current_publication
    checks = {
        "references": _check_references(pub, network=network),
        "similarity": _check_similarity(submission, pub),
        "emails": _check_emails(submission, pub),
        "self_citation": _check_self_citation(pub),
        "orcid": _check_orcid(pub),
    }
    order = {"alert": 0, "warn": 1, "info": 2, "ok": 3}
    worst = min((c["status"] for c in checks.values()), key=lambda s: order[s])
    report = {"overall": worst, "network": network,
              "generated_at": timezone.now().isoformat(timespec="seconds"),
              "checks": checks}
    submission.integrity_report = report
    submission.integrity_checked_at = timezone.now()
    submission.save(update_fields=["integrity_report", "integrity_checked_at"])
    return report


def run_checks_job(submission_id: int, network: bool = True) -> dict:
    """Kuyruğa uygun sarmalayıcı."""
    from .models import Submission
    sub = Submission.objects.filter(pk=submission_id).first()
    if not sub:
        return {"ok": False, "reason": "missing"}
    report = run_checks(sub, network=network)
    return {"ok": True, "overall": report["overall"]}
