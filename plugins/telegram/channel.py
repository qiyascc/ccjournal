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

"""Telegram bildirim kanalı — e-postadan bağımsız.

Alıcı e-postalardan kullanıcıları bulur; telegram_id'si olanlara, aynı şablon
içeriğini doğrudan Telegram Bot API üzerinden iletir. Bot'un çalışıyor olması
gerekmez — token yeterlidir.
"""
from __future__ import annotations

from apps.comms.channels import NotificationChannel


class TelegramChannel(NotificationChannel):
    key = "telegram"
    name = "Telegram"

    def is_available(self, journal) -> bool:
        from apps.plugins.registry import registry
        if not registry.is_enabled("telegram"):
            return False
        from . import client
        return bool(client.token())

    def deliver(self, *, key, journal, locale, to, subject, body,
                context=None, related=None) -> tuple[bool, str]:
        from . import client
        from apps.accounts.models import User
        chats = (User.objects.filter(email__in=list(to))
                 .exclude(telegram_id="")
                 .values_list("telegram_id", flat=True))
        if not chats:
            return False, "no telegram recipients"
        text = f"*{subject}*\n\n{body}" if subject else body
        if key == "review_request":
            text += "\n\n\u21a9 Reply 1 to ACCEPT or 2 to DECLINE this invitation."
        sent_any, last_err = False, ""
        for chat_id in chats:
            ok, err = client.send(chat_id, text)
            sent_any = sent_any or ok
            if not ok:
                last_err = err
        return sent_any, last_err
