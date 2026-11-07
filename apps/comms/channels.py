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

"""Bildirim kanalları — çok-kanallı notification dağıtımı.

Bir bildirim **tek bir kaynaktan** (e-posta şablonu) üretilir, sonra kayıtlı tüm
aktif **kanallara** dağıtılır: e-posta, WhatsApp, (gelecekte) Telegram, Slack…
E-posta artık ayrıcalıklı değil — yalnızca yerleşik bir kanaldır. Mail ayarı
olmasa bile diğer kanallar (WhatsApp vb.) çalışır.

Yeni kanal eklemek: `NotificationChannel`'ı türet, `deliver()` yaz, registry'ye
kaydet (plugin'ler bunu `register()` içinde yapar; yerleşik e-posta otomatik kayıtlı).

Adresleme: kanallara `to` (e-posta listesi) geçilir — bu kullanıcı kimliğidir.
Her kanal bu kimlikten kendi adres alanını çözer (e-posta→email, WhatsApp→numara,
Telegram→chat_id). Böylece tek çağrı tüm kanallara uygun şekilde ulaşır.
"""
from __future__ import annotations


class NotificationChannel:
    """Tüm kanalların temel sınıfı."""
    key: str = ""
    name: str = ""

    def is_available(self, journal) -> bool:
        """Bu kanal şu an gönderim yapabilir mi? (ayar/bağlantı kontrolü)"""
        return True

    def deliver(self, *, key, journal, locale, to, subject, body,
                context=None, related=None) -> tuple[bool, str]:
        """Bildirimi ilet. (ok, hata) döndür. Alt sınıf override eder."""
        raise NotImplementedError


class ChannelRegistry:
    """Kayıtlı bildirim kanalları. Yerleşik 'email' + plugin kanalları."""

    def __init__(self):
        self._channels: dict[str, NotificationChannel] = {}

    def register(self, channel: NotificationChannel) -> None:
        if not getattr(channel, "key", ""):
            raise ValueError("Channel 'key' tanımlı olmalı.")
        self._channels[channel.key] = channel

    def unregister(self, key: str) -> None:
        self._channels.pop(key, None)

    def get(self, key: str):
        return self._channels.get(key)

    def all(self) -> list[NotificationChannel]:
        return list(self._channels.values())

    def active(self, journal) -> list[NotificationChannel]:
        """Şu an gönderim yapabilen kanallar."""
        out = []
        for ch in self._channels.values():
            try:
                if ch.is_available(journal):
                    out.append(ch)
            except Exception:
                pass
        return out


registry = ChannelRegistry()


class EmailChannel(NotificationChannel):
    key = "email"
    name = "Email"

    def is_available(self, journal) -> bool:
        """E-posta backend'i yapılandırılmışsa kullanılabilir.

        Konsol/locmem/SMTP backend'leri 'mevcut' sayılır; yalnızca backend hiç
        ayarlanmamışsa (dummy) devre dışı kalır.
        """
        from django.conf import settings
        backend = getattr(settings, "EMAIL_BACKEND", "")
        if "dummy" in backend:
            return False
        if backend.endswith("smtp.EmailBackend"):
            return bool(getattr(settings, "EMAIL_HOST", ""))
        return True

    def deliver(self, *, key, journal, locale, to, subject, body,
                context=None, related=None) -> tuple[bool, str]:
        from django.conf import settings
        from django.core.mail import send_mail
        from .services import MailService
        if not to:
            return False, "no recipients"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.org")
        html_body = MailService._html(subject, body, journal)
        status, error = "sent", ""
        try:
            sent = send_mail(subject, body, from_email, list(to),
                             fail_silently=False, html_message=html_body)
            if not sent:
                status, error = "failed", "send_mail returned 0"
        except Exception as exc:  # noqa: BLE001
            status, error = "failed", str(exc)
        MailService._log(key, journal, locale, from_email, list(to), subject, body,
                         status, error, related)
        return status == "sent", error


registry.register(EmailChannel())
