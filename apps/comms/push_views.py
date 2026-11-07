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

"""Tarayıcı push aboneliği kayıt ucu (yalnız staff)."""
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@staff_member_required
def subscribe(request):
    if request.method != "POST":
        return JsonResponse({"detail": "POST only"}, status=405)
    try:
        sub = json.loads(request.body)
        endpoint = sub["endpoint"]
        keys = sub.get("keys", {})
        from push_notifications.models import WebPushDevice
        WebPushDevice.objects.update_or_create(
            registration_id=endpoint,
            defaults={"user": request.user, "p256dh": keys.get("p256dh", ""),
                      "auth": keys.get("auth", ""), "browser": "CHROME", "active": True})
        return JsonResponse({"ok": True})
    except Exception as e:  # noqa: BLE001
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
