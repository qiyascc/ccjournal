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

"""WhatsApp bildirim kanalı.

E-postadan bağımsız bir kanal: NotificationService bir bildirim dağıttığında, bu
kanal alıcı e-postalardan kullanıcıları bulur ve WhatsApp numarası olanlara aynı
içeriği iletir. E-posta ayarı olmasa bile çalışır.
"""
from __future__ import annotations

from apps.comms.channels import NotificationChannel


class WhatsAppChannel(NotificationChannel):
    key = "whatsapp"
    name = "WhatsApp"

    def is_available(self, journal) -> bool:
        """Plugin etkin ve sidecar bağlı (oturum açık) ise kullanılabilir."""
        from apps.plugins.registry import registry
        if not registry.is_enabled("whatsapp"):
            return False
        from . import client
        return client.status().get("status") == "connected"

    def deliver(self, *, key, journal, locale, to, subject, body,
                context=None, related=None) -> tuple[bool, str]:
        from . import client
        from apps.accounts.models import User
        numbers = (User.objects.filter(email__in=list(to))
                   .exclude(whatsapp_number="")
                   .values_list("whatsapp_number", flat=True))
        if not numbers:
            return False, "no whatsapp recipients"
        text = f"*{subject}*\n\n{body}" if subject else body
        if key == "review_request":
            text += "\n\n\u21a9 Reply 1 to ACCEPT or 2 to DECLINE this invitation."
        sent_any, last_err = False, ""
        for number in numbers:
            ok, err = client.send(number, text)
            sent_any = sent_any or ok
            if not ok:
                last_err = err
        return sent_any, last_err
