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
ORCID ile giriş (OAuth2 authorization-code, /authenticate kapsamı).

Config-gated: [orcid] client_id/client_secret verilmezse tamamen kapalıdır
(buton gizli, uçlar 400 döner). ORCID token yanıtı iD + adı doğrudan içerir,
ek API çağrısı gerekmez. Kullanıcı orcid alanına göre eşlenir; yoksa oluşturulur
(SSO-only, kullanılamaz parola; e-posta profilden güncellenir).
"""
from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger("ccjournal.accounts")

_MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"


def _cfg() -> dict:
    return getattr(settings, "ORCID", {}) or {}


def is_configured() -> bool:
    c = _cfg()
    return bool(c.get("client_id") and c.get("client_secret"))


def _base() -> str:
    return "https://sandbox.orcid.org" if _cfg().get("sandbox") else "https://orcid.org"


def _redirect_uri(request) -> str:
    return request.build_absolute_uri(reverse("orcid_callback"))


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def authorize_url(request) -> str:
    state = secrets.token_urlsafe(24)
    request.session["orcid_state"] = state
    scope = "/authenticate"
    if _cfg().get("push"):
        scope = "/authenticate /activities/update"
    params = {
        "client_id": _cfg()["client_id"],
        "response_type": "code",
        "scope": scope,
        "redirect_uri": _redirect_uri(request),
        "state": state,
    }
    return f"{_base()}/oauth/authorize?{urlencode(params)}"


def exchange_code(request, code: str) -> dict:
    import requests
    resp = requests.post(
        f"{_base()}/oauth/token",
        data={"client_id": _cfg()["client_id"], "client_secret": _cfg()["client_secret"],
              "grant_type": "authorization_code", "code": code,
              "redirect_uri": _redirect_uri(request)},
        headers={"Accept": "application/json"}, timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def resolve_user(orcid: str, name: str = ""):
    """orcid'e göre kullanıcı bulur; yoksa oluşturur. (user, created) döner."""
    from .models import User
    existing = User.objects.filter(orcid=orcid).first()
    if existing:
        return existing, False
    given, family = _split_name(name)
    user = User.objects.create_user(
        email=f"{orcid}@orcid.local", password=None,
        given_name=given or orcid, family_name=family, orcid=orcid,
    )
    return user, True


def orcid_login(request):
    if not is_configured():
        return HttpResponseBadRequest("ORCID login is not configured.")
    return HttpResponseRedirect(authorize_url(request))


def orcid_callback(request):
    if not is_configured():
        return HttpResponseBadRequest("ORCID login is not configured.")
    state = request.GET.get("state")
    if not state or state != request.session.pop("orcid_state", None):
        return HttpResponseBadRequest("Invalid OAuth state.")
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing authorization code.")
    try:
        data = exchange_code(request, code)
    except Exception:
        logger.warning("ORCID token exchange failed", exc_info=True)
        return HttpResponseBadRequest("ORCID authentication failed.")
    orcid = data.get("orcid")
    if not orcid:
        return HttpResponseBadRequest("ORCID did not return an iD.")
    user, _created = resolve_user(orcid, data.get("name", ""))
    if not user.is_active:
        return HttpResponseBadRequest("This account is disabled.")
    token = data.get("access_token", "")
    scope = data.get("scope", "")
    if token and (user.orcid_access_token != token or user.orcid_token_scope != scope):
        user.orcid_access_token = token
        user.orcid_token_scope = scope
        user.save(update_fields=["orcid_access_token", "orcid_token_scope"])
    auth_login(request, user, backend=_MODEL_BACKEND)
    return redirect(settings.LOGIN_REDIRECT_URL)
