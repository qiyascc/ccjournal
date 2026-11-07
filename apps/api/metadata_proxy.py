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

"""ROR + Crossref Funder autocomplete proxy'leri.

CSP `connect-src 'self'` olduğu için tarayıcı dış API'ye çıkamaz; bu uçlar
sorguyu sunucudan yapar, ince JSON döndürür ve 1 saat cache'ler. Girişli
kullanıcıya açıktır (wizard + admin); dış API'ler ücretsiz/anahtarsızdır.
"""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse

ROR_URL = "https://api.ror.org/v2/organizations?query={q}"
FUNDER_URL = "https://api.crossref.org/funders?query={q}&rows=8"
CACHE_TTL = 3600


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "ccjournal-autocomplete", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


@login_required
def ror_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"results": []})
    key = "ror:" + hashlib.md5(q.lower().encode()).hexdigest()
    hit = cache.get(key)
    if hit is None:
        try:
            data = _fetch_json(ROR_URL.format(q=urllib.parse.quote(q)))
            hit = [{"name": next((n["value"] for n in it.get("names", [])
                                  if "ror_display" in (n.get("types") or [])),
                                 (it.get("names") or [{}])[0].get("value", "")),
                    "ror": it.get("id", ""),
                    "country": ((it.get("locations") or [{}])[0]
                                .get("geonames_details", {}).get("country_name", ""))}
                   for it in (data.get("items") or [])[:8]]
        except Exception:
            hit = []
        cache.set(key, hit, CACHE_TTL)
    return JsonResponse({"results": hit})


@login_required
def funder_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"results": []})
    key = "funder:" + hashlib.md5(q.lower().encode()).hexdigest()
    hit = cache.get(key)
    if hit is None:
        try:
            data = _fetch_json(FUNDER_URL.format(q=urllib.parse.quote(q)))
            hit = [{"name": it.get("name", ""),
                    "id": f"10.13039/{it.get('id')}" if it.get("id") else ""}
                   for it in (data.get("message", {}).get("items") or [])]
        except Exception:
            hit = []
        cache.set(key, hit, CACHE_TTL)
    return JsonResponse({"results": hit})
