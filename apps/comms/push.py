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

"""Web Push (tarayıcı bildirimi) yardımcıları — django-push-notifications/WebPush.

VAPID anahtarları config.ini [push] bölümünden gelir; anahtar yoksa sessizce atlanır.
"""
from __future__ import annotations

import json


def push_to_user(user, title: str, body: str, url: str = "/admin/") -> int:
    """Kullanıcının kayıtlı tarayıcılarına push gönderir; gönderilen cihaz sayısı döner."""
    try:
        from django.conf import settings
        if not settings.PUSH_NOTIFICATIONS_SETTINGS.get("WP_PRIVATE_KEY"):
            return 0
        from push_notifications.models import WebPushDevice
        devices = WebPushDevice.objects.filter(user=user, active=True)
        payload = json.dumps({"title": title, "body": body, "url": url})
        n = 0
        for d in devices:
            try:
                d.send_message(payload)
                n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


def push_to_superusers(title: str, body: str, url: str = "/admin/") -> int:
    try:
        from apps.accounts.models import User
        return sum(push_to_user(u, title, body, url)
                   for u in User.objects.filter(is_superuser=True, is_active=True))
    except Exception:
        return 0
