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

"""ORCID push — yayımlanan makaleyi yazarın ORCID kaydına "work" olarak yazar.

Config-gated: [orcid] push=true VE üye (member) API kimlik bilgileri gerekir.
Kapsam akışı: push açıkken ORCID girişi /activities/update kapsamı ister; token
kullanıcıda saklanır. Yayın yayımlanınca, yayının ORCID'li yazarlarıyla eşleşen
ve geçerli token+kapsamı olan kullanıcıların kayıtlarına work POST edilir.
Public API kimlik bilgileriyle ORCID isteği 403 ile reddeder — hata loglanır.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger("ccjournal.accounts")

UPDATE_SCOPE = "/activities/update"


def push_enabled() -> bool:
    c = getattr(settings, "ORCID", {}) or {}
    return bool(c.get("push") and c.get("client_id") and c.get("client_secret"))


def _api_base() -> str:
    c = getattr(settings, "ORCID", {}) or {}
    return ("https://api.sandbox.orcid.org" if c.get("sandbox")
            else "https://api.orcid.org")


def work_payload(publication) -> dict:
    """ORCID v3.0 work JSON'u (title, journal, tarih, DOI, URL)."""
    from apps.comms.utils import absolute_url

    journal = publication.submission.journal
    jt = (journal.translations.filter(locale=journal.primary_locale).first()
          or journal.translations.first())
    t = (publication.translations.filter(locale=publication.primary_locale).first()
         or publication.translations.first())
    payload: dict = {
        "title": {"title": {"value": (t.title if t else "Untitled")}},
        "journal-title": {"value": (jt.title if jt else journal.path)},
        "type": "journal-article",
        "url": {"value": absolute_url(f"/article/{publication.submission_id}/")},
    }
    if publication.date_published:
        payload["publication-date"] = {
            "year": {"value": str(publication.date_published.year)},
            "month": {"value": f"{publication.date_published.month:02d}"},
            "day": {"value": f"{publication.date_published.day:02d}"},
        }
    if publication.doi_id:
        payload["external-ids"] = {"external-id": [{
            "external-id-type": "doi",
            "external-id-value": publication.doi.doi,
            "external-id-relationship": "self",
        }]}
    return payload


def _post_work(orcid: str, token: str, payload: dict) -> tuple[bool, str]:
    req = urllib.request.Request(
        f"{_api_base()}/v3.0/{orcid}/work",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/vnd.orcid+json",
                 "Accept": "application/json",
                 "Authorization": f"Bearer {token}",
                 "User-Agent": "ccjournal-orcid-push"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201), f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, str(exc.reason)


def push_publication(publication_id: int) -> dict:
    """Kuyruğa uygun iş: yayının ORCID'li yazarlarına work yazar."""
    from apps.publications.models import Publication

    if not push_enabled():
        return {"pushed": 0, "reason": "orcid push disabled"}
    pub = (Publication.objects.filter(id=publication_id)
           .select_related("submission__journal", "doi")
           .prefetch_related("authors", "translations").first())
    if not pub:
        return {"pushed": 0, "reason": "publication missing"}

    from .models import User
    orcids = {a.orcid for a in pub.authors.all() if a.orcid}
    if not orcids:
        return {"pushed": 0, "reason": "no orcid authors"}
    payload = work_payload(pub)
    pushed = failed = skipped = 0
    for orcid in sorted(orcids):
        user = User.objects.filter(orcid=orcid).exclude(orcid_access_token="").first()
        if not user or UPDATE_SCOPE not in (user.orcid_token_scope or ""):
            skipped += 1
            continue
        ok, detail = _post_work(orcid, user.orcid_access_token, payload)
        if ok:
            pushed += 1
            logger.info("ORCID push ok for %s (%s)", orcid, detail)
        else:
            failed += 1
            logger.warning("ORCID push failed for %s: %s", orcid, detail)
    return {"pushed": pushed, "failed": failed, "skipped": skipped}
