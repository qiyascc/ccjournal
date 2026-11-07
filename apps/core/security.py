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
Güvenlik başlıkları middleware'i (bağımlılıksız).

Site tamamen self-host olduğundan (CDN yok), sıkı bir Content-Security-Policy
uygulanabilir: harici script/style/font/frame kaynakları engellenir. Inline
script/style ve CKEditor'ün blob:/data: ihtiyaçları korunur.

Ayarlar (settings; config.ini [security]'den beslenir):
  CSP_POLICY        -> tam politika dizesi (boşsa CSP başlığı eklenmez)
  CSP_REPORT_ONLY   -> True ise yalnız rapor (engellemez)
  REFERRER_POLICY / PERMISSIONS_POLICY
"""
from __future__ import annotations

from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = getattr(settings, "CSP_POLICY", "") or ""
        self.csp_header = ("Content-Security-Policy-Report-Only"
                           if getattr(settings, "CSP_REPORT_ONLY", False)
                           else "Content-Security-Policy")
        self.referrer = getattr(settings, "REFERRER_POLICY", "strict-origin-when-cross-origin")
        self.permissions = getattr(settings, "PERMISSIONS_POLICY",
                                   "geolocation=(), microphone=(), camera=()")

    def __call__(self, request):
        response = self.get_response(request)
        if self.csp and not response.has_header(self.csp_header):
            response[self.csp_header] = self.csp
        if self.referrer and not response.has_header("Referrer-Policy"):
            response["Referrer-Policy"] = self.referrer
        if self.permissions and not response.has_header("Permissions-Policy"):
            response["Permissions-Policy"] = self.permissions
        return response
