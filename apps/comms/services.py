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
İletişim servisleri + özel iş-akışı sinyalleri.

Servisler (MailService, NotifyService) "nasıl" gönderileceğini bilir; sinyaller
"ne zaman" tetikleneceğini bağlar (receivers.py). Böylece iş kuralları (services.py)
iletişimden bağımsız kalır — istersen e-postayı kapatır, başka kanal eklersin.
"""
from __future__ import annotations

from django.db.models import Q
from django.dispatch import Signal
from django.template import Context, Template

from .models import EmailTemplate, Notification

submission_created = Signal()
decision_recorded = Signal()
review_assigned = Signal()
publication_published = Signal()


class MailService:
    @staticmethod
    def _resolve(key: str, journal, locale: str) -> EmailTemplate | None:
        qs = EmailTemplate.objects.filter(key=key, enabled=True)
        for jrnl, loc in [(journal, locale), (journal, "en"), (None, locale), (None, "en")]:
            cond = Q(locale=loc)
            cond &= Q(journal=jrnl) if jrnl else Q(journal__isnull=True)
            tpl = qs.filter(cond).first()
            if tpl:
                return tpl
        return None

    @staticmethod
    def render(key: str, *, journal, locale: str, context: dict) -> tuple[str, str] | None:
        tpl = MailService._resolve(key, journal, locale)
        if not tpl:
            return None
        from apps.plugins.hooks import hooks
        context = hooks.apply_filters("email.context", dict(context), key=key, journal=journal)
        ctx = Context(context)
        subject = Template(tpl.subject).render(ctx)
        body = Template(tpl.body).render(ctx)
        body = hooks.apply_filters("email.body", body, key=key, journal=journal)
        return subject, body

    @staticmethod
    def send(key: str, *, journal, locale: str, to: list[str], context: dict,
             related=None) -> bool:
        """Geriye dönük uyum: tüm bildirim kanallarına dağıtır (e-posta dahil).

        Eskiden yalnız e-posta gönderirdi; artık NotificationService üzerinden tüm
        aktif kanallara (e-posta, WhatsApp, …) iletir. Dönüş: en az bir kanal başarılı.
        """
        results = NotificationService.notify(key, journal=journal, locale=locale,
                                             to=to, context=context, related=related)
        return any(ok for ok, _ in results.values())

    @staticmethod
    def _html(subject, body, journal):
        try:
            from django.template.loader import render_to_string
            from django.utils.html import linebreaks
            title = None
            if journal is not None:
                try:
                    from apps.journals.models import JournalTranslation
                    row = (JournalTranslation.objects.filter(
                               journal=journal, locale=journal.primary_locale).first()
                           or JournalTranslation.objects.filter(journal=journal).first())
                    title = row.title if row else None
                except Exception:
                    title = None
            site_url = ""
            try:
                from apps.configuration.services import Config
                site_url = Config.get("general", "site_url", "")
            except Exception:
                site_url = ""
            return render_to_string("email/base_email.html", {
                "subject": subject, "body_html": linebreaks(body),
                "journal_title": title or "Journal", "site_url": site_url,
            })
        except Exception:
            return None

    @staticmethod
    def _log(key, journal, locale, from_email, to, subject, body, status, error, related):
        try:
            from django.contrib.contenttypes.models import ContentType
            from .models import EmailLog
            ct = obj_id = None
            if related is not None and getattr(related, "pk", None):
                ct = ContentType.objects.get_for_model(related.__class__)
                obj_id = related.pk
            EmailLog.objects.create(
                journal=journal, template_key=key or "", locale=locale or "",
                from_email=from_email, to_emails=", ".join(to), subject=subject,
                body=body, status=status, error=error,
                content_type=ct, object_id=obj_id)
        except Exception:
            pass


class NotificationService:
    """Çok-kanallı bildirim dağıtıcısı.

    Şablonu **tek kaynaktan** (e-posta şablonu) bir kez render eder, sonra kayıtlı
    tüm aktif kanallara (e-posta, WhatsApp, gelecekte Telegram/Slack) dağıtır. Bir
    kanalın başarısı/başarısızlığı diğerlerini etkilemez. E-posta yalnızca bir
    kanaldır; ayarı yoksa bile diğer kanallar çalışır.
    """

    @staticmethod
    def notify(key: str, *, journal, locale: str, to: list[str], context: dict,
               related=None, channels: list[str] | None = None) -> dict[str, tuple[bool, str]]:
        """key şablonunu render edip aktif kanallara dağıtır.

        `channels` verilirse yalnız o anahtarlardaki kanallara gönderilir; aksi halde
        tüm aktif kanallara. Dönüş: {channel_key: (ok, error)}.
        """
        rendered = MailService.render(key, journal=journal, locale=locale, context=context)
        if not rendered or not to:
            return {}
        subject, body = rendered

        from .channels import registry as channel_registry
        targets = channel_registry.active(journal)
        if channels is not None:
            targets = [c for c in targets if c.key in channels]

        results: dict[str, tuple[bool, str]] = {}
        for ch in targets:
            try:
                ok, err = ch.deliver(key=key, journal=journal, locale=locale, to=to,
                                     subject=subject, body=body, context=context,
                                     related=related)
                results[ch.key] = (bool(ok), err or "")
            except Exception as exc:  # noqa: BLE001
                results[ch.key] = (False, str(exc))
                import logging
                logging.getLogger("comms").exception(
                    "channel %s delivery failed", ch.key)
        return results

    @staticmethod
    def notify_raw(*, journal, to: list[str], subject: str, body: str,
                   key: str = "custom", related=None,
                   channels: list[str] | None = None) -> dict[str, tuple[bool, str]]:
        """Önceden hazır (şablonsuz) içeriği aktif kanallara dağıtır.

        Editörün düzenlediği karar e-postaları gibi 'insan yazdı' içerikler için:
        render adımı atlanır; loglama/kanal davranışı aynen korunur.
        """
        if not to or not subject:
            return {}
        from .channels import registry as channel_registry
        targets = channel_registry.active(journal)
        if channels is not None:
            targets = [c for c in targets if c.key in channels]
        results: dict[str, tuple[bool, str]] = {}
        for ch in targets:
            try:
                ok, err = ch.deliver(key=key, journal=journal, locale="", to=to,
                                     subject=subject, body=body, context={},
                                     related=related)
                results[ch.key] = (bool(ok), err or "")
            except Exception as exc:  # noqa: BLE001
                results[ch.key] = (False, str(exc))
        return results


class NotifyService:
    @staticmethod
    def create(recipient, type: str, title: str, *, body="", url="", journal=None) -> Notification:
        return Notification.objects.create(
            recipient=recipient, type=type, title=title, body=body, url=url, journal=journal
        )

    @staticmethod
    def unread_count(user) -> int:
        return user.notifications.filter(is_read=False).count()
