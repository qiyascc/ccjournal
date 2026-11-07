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

"""Crossref DOI deposit — gerçek HTTP gönderimi + durum güncelleme.

Crossref'in deposit API'sine doi_batch XML'i POST eder, Doi kayıtlarının
durumunu (SUBMITTED/REGISTERED/ERROR) günceller. Kimlik bilgileri yoksa
güvenli biçimde "dry-run" döner (XML üretir ama göndermez).

Crossref akışı asenkrondur: deposit kabul edilince HTTP 200 döner ama tescil
arka planda tamamlanır. Bu yüzden başarılı gönderim SUBMITTED'a çeker;
REGISTERED'a geçiş, submission log sorgusuyla (poll_status) doğrulanır.
"""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone

PROD_URL = "https://doi.crossref.org/servlet/deposit"
TEST_URL = "https://test.crossref.org/servlet/deposit"
PROD_STATUS = "https://doi.crossref.org/servlet/submissionDownload"
TEST_STATUS = "https://test.crossref.org/servlet/submissionDownload"


def _conf():
    return getattr(settings, "CROSSREF", {})


def is_configured() -> bool:
    c = _conf()
    return bool(c.get("username") and c.get("password"))


def deposit_publications(publications, *, depositor=None) -> dict:
    """Yayınları tek doi_batch içinde Crossref'e gönderir.

    Dönen sözlük: {ok, submitted, batch_id, dry_run, status_code, detail, dois}.
    Kimlik bilgisi yoksa dry_run=True ile yalnız XML üretir (gönderim yok).
    """
    from .serializers import to_crossref_deposit
    pubs = [p for p in publications if p.doi_id]
    if not pubs:
        return {"ok": False, "detail": "No publications with a DOI to deposit.",
                "submitted": 0, "dry_run": True, "dois": []}

    xml_obj = to_crossref_deposit(pubs, depositor=depositor)
    if isinstance(xml_obj, (bytes, bytearray)):
        xml_bytes = bytes(xml_obj)
    elif isinstance(xml_obj, str):
        xml_bytes = xml_obj.encode("utf-8")
    else:
        from lxml import etree
        xml_bytes = etree.tostring(xml_obj, xml_declaration=True,
                                   encoding="UTF-8", pretty_print=True)

    c = _conf()
    dois = []
    for p in pubs:
        dois.append(p.doi)
        for g in p.galleys.all():
            if g.doi_id:
                dois.append(g.doi)

    if not is_configured():
        return {"ok": False, "dry_run": True, "submitted": 0,
                "detail": "Crossref credentials are not set (config.ini [crossref]). "
                          "XML generated but not sent.",
                "xml": xml_bytes.decode("utf-8", "replace"),
                "dois": [d.doi for d in dois]}

    url = TEST_URL if c.get("test_mode") else PROD_URL
    import requests
    try:
        resp = requests.post(
            url,
            params={"operation": "doMDUpload",
                    "login_id": c["username"], "login_passwd": c["password"]},
            files={"fname": ("deposit.xml", xml_bytes, "application/xml")},
            timeout=30,
        )
        ok = resp.status_code == 200
        from apps.core.models.identifiers import Doi
        for d in dois:
            d.agency = Doi.Agency.CROSSREF
            d.status = Doi.Status.SUBMITTED if ok else Doi.Status.ERROR
            d.last_response = {"http_status": resp.status_code,
                               "body": resp.text[:2000],
                               "at": timezone.now().isoformat()}
            d.save(update_fields=["agency", "status", "last_response"])
        return {"ok": ok, "dry_run": False, "submitted": len(dois) if ok else 0,
                "status_code": resp.status_code,
                "detail": ("Deposit accepted — DOIs marked SUBMITTED. "
                           "Crossref finalises registration asynchronously."
                           if ok else f"Crossref returned HTTP {resp.status_code}."),
                "dois": [d.doi for d in dois]}
    except Exception as e:  # noqa: BLE001
        from apps.core.models.identifiers import Doi
        for d in dois:
            d.status = Doi.Status.ERROR
            d.last_response = {"error": str(e), "at": timezone.now().isoformat()}
            d.save(update_fields=["status", "last_response"])
        return {"ok": False, "dry_run": False, "submitted": 0,
                "detail": f"Deposit failed: {e}", "dois": [d.doi for d in dois]}
