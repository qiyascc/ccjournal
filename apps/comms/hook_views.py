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

"""Gelen kanal mesajları webhook'u — /hooks/channel-reply/ (yalnız yerel sidecar).

WhatsApp sidecar'ı (Node) gelen mesajı buraya POST'lar:
    {"channel": "whatsapp", "address": "9945xxxxxxx", "text": "1"}
Başlık: X-CCJ-Hook-Secret == config.ini [channels] hook_secret (ilk kullanımda
otomatik üretilir). Yanıt: {"reply": "..."} — sidecar kullanıcıya geri yazar.
Telegram botu Django ORM'e doğrudan bağlı olduğundan bu webhook'u kullanmaz.
"""
from __future__ import annotations

import json
import logging
import re

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger("ccjournal.comms")


def hook_secret() -> str:
    """Paylaşılan sır — yoksa üretilip config'e yazılır (dosya+DB).

    Testler dosyaya dokunmasın diye settings.CHANNEL_HOOK_SECRET öncelikli."""
    from django.conf import settings
    override = getattr(settings, "CHANNEL_HOOK_SECRET", "")
    if override:
        return override
    from apps.configuration.services import Config
    secret = (Config.get("channels", "hook_secret", "") or "").strip()
    if not secret:
        import secrets as _secrets
        secret = _secrets.token_urlsafe(24)
        try:
            Config.set("channels", "hook_secret", secret)
        except Exception:
            logger.warning("could not persist hook secret", exc_info=True)
    return secret


def _user_for(channel: str, address: str):
    from apps.accounts.models import User
    if channel == "telegram":
        return User.objects.filter(telegram_id=str(address)).first()
    digits = re.sub(r"\D", "", address or "")
    if not digits:
        return None
    return (User.objects.filter(whatsapp_number=digits).first()
            or User.objects.filter(whatsapp_number__endswith=digits[-9:]).first())


@csrf_exempt
@require_POST
def channel_reply(request):
    if request.headers.get("X-CCJ-Hook-Secret", "") != hook_secret():
        return HttpResponse(status=403)
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "bad json"}, status=400)
    channel = (data.get("channel") or "").strip().lower()
    address = (data.get("address") or "").strip()
    text = data.get("text") or ""
    user = _user_for(channel, address)
    if user is None:
        return JsonResponse({"reply": ""})
    from apps.review.quick_response import handle_reply
    reply = handle_reply(user, text)
    return JsonResponse({"reply": reply or ""})
