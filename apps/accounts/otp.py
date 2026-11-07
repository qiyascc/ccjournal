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

"""İki adımlı doğrulama (2FA / OTP) — django-otp + Google Authenticator (TOTP).

Opsiyonel ve **varsayılan kapalı** (settings.OTP_ENABLED). Açıkken yalnız
**Developer + superuser** için zorunludur; diğer kullanıcılar etkilenmez.

Akış: bu roldeki bir kullanıcı admin'e girer → doğrulanmamışsa OTP sayfasına
yönlendirilir → cihazı yoksa QR ile Google Authenticator'a ekler, kodu girer →
doğrulanır ve admin'e devam eder.
"""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


def otp_enabled() -> bool:
    """2FA açık mı? Önce runtime ayarı (constance, adminden değişir), yoksa config.ini.

    Böylece sunucuyu yeniden başlatmadan adminden anında açılıp kapanabilir.
    """
    try:
        from constance import config
        return bool(config.OTP_ENABLED)
    except Exception:
        return bool(getattr(settings, "OTP_ENABLED", False))


def otp_required_for(user) -> bool:
    """Bu kullanıcı için 2FA zorunlu mu? (yalnız Developer + superuser)."""
    if not otp_enabled():
        return False
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        return "Developer" in user.role_names
    except Exception:
        return False


def _is_verified(user) -> bool:
    fn = getattr(user, "is_verified", None)
    return bool(fn() if callable(fn) else False)


class OTPEnforcementMiddleware:
    """OTP zorunlu kullanıcıları, admin'e erişmeden önce doğrulamaya zorlar.

    Sadece /admin/ alanını korur (asıl yönetim yüzeyi). OTP setup/verify ve logout
    yolları muaftır (yoksa yönlendirme döngüsü olur).
    """

    EXEMPT_PREFIXES = ("/admin/otp/", "/admin/login/", "/admin/logout/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if otp_enabled():
            path = request.path
            if path.startswith("/admin/") and not path.startswith(self.EXEMPT_PREFIXES):
                user = getattr(request, "user", None)
                if user is not None and otp_required_for(user) and not _is_verified(user):
                    return redirect(f"{reverse('otp_setup')}?next={path}")
        return self.get_response(request)
