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

"""OTP kurulum/doğrulama görünümleri (Google Authenticator / TOTP)."""
from __future__ import annotations

import base64
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from .otp import otp_required_for


def _safe_next(request) -> str:
    nxt = request.GET.get("next") or request.POST.get("next") or "/admin/"
    return nxt if nxt.startswith("/") else "/admin/"


def _qr_data_url(otpauth_url: str) -> str:
    import qrcode
    img = qrcode.make(otpauth_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@login_required
def otp_setup(request):
    """Kullanıcının doğrulanmamış TOTP cihazını (yoksa) kurar; doğrulanmış cihazı
    olan ama oturumu doğrulanmamışsa kod ister. Developer/superuser dışı için no-op."""
    from django_otp.plugins.otp_totp.models import TOTPDevice

    user = request.user
    nxt = _safe_next(request)

    if not otp_required_for(user):
        return HttpResponseRedirect(nxt)

    if user.is_verified():
        return HttpResponseRedirect(nxt)

    confirmed = TOTPDevice.objects.filter(user=user, confirmed=True).first()
    if confirmed:
        return _verify(request, confirmed, nxt, mode="verify")

    device = (TOTPDevice.objects.filter(user=user, confirmed=False).first()
              or TOTPDevice.objects.create(user=user, confirmed=False,
                                           name=f"{settings.OTP_TOTP_ISSUER} ({user.email})"))
    return _verify(request, device, nxt, mode="setup")


_MAX_ATTEMPTS = 5
_ATTEMPT_KEY = "otp_attempts"


def _verify(request, device, nxt, *, mode):
    error = ""
    if request.method == "POST":
        token = (request.POST.get("token") or "").strip().replace(" ", "")
        if device.verify_token(token):
            if mode == "setup" and not device.confirmed:
                device.confirmed = True
                device.save()
            from django_otp import login as otp_login
            otp_login(request, device)
            request.session.pop(_ATTEMPT_KEY, None)
            messages.success(request, _("Two-factor authentication verified."))
            return HttpResponseRedirect(nxt)
        attempts = int(request.session.get(_ATTEMPT_KEY, 0)) + 1
        request.session[_ATTEMPT_KEY] = attempts
        remaining = _MAX_ATTEMPTS - attempts
        if attempts >= _MAX_ATTEMPTS:
            from django.contrib.auth import logout as auth_logout
            request.session.pop(_ATTEMPT_KEY, None)
            auth_logout(request)
            messages.error(request, _("Too many incorrect codes. Please sign in again."))
            return HttpResponseRedirect(reverse("admin:login") + f"?next={nxt}")
        error = _("Invalid code. %(n)s attempt(s) left.") % {"n": remaining}

    ctx = {"mode": mode, "error": error, "next": nxt,
           "issuer": settings.OTP_TOTP_ISSUER}
    if mode == "setup":
        url = device.config_url
        if "issuer=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}issuer={settings.OTP_TOTP_ISSUER}"
        ctx["qr"] = _qr_data_url(url)
        ctx["secret"] = base64.b32encode(device.bin_key).decode("ascii").rstrip("=")
    return render(request, "registration/otp.html", ctx)
