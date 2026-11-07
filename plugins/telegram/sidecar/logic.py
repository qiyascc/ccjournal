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

"""Telegram bot iş mantığı — Django ORM ile (saf, test edilebilir fonksiyonlar).

Polling bot (bot.py) yalnızca Telegram olaylarını bu fonksiyonlara bağlar; tüm
veri/yetki mantığı burada, böylece gerçek Telegram olmadan test edilebilir.
"""
from __future__ import annotations


def link_account_by_token(token: str, chat_id: str, username: str = "") -> dict | None:
    """Bağlama anahtarından kullanıcıyı bulur ve telegram_id'yi atar.

    Dönüş: kullanıcı bilgisi {name, email, roles} ya da geçersizse None.
    Zaten bağlıysa {already: True, name} döner.
    """
    from apps.accounts.models import User
    token = (token or "").strip()
    if not token:
        return None
    user = User.objects.filter(telegram_link_token=token).first()
    if not user:
        return None
    if user.telegram_id == str(chat_id):
        return {"already": True, "name": user.full_name}
    user.telegram_id = str(chat_id)
    if username:
        user.telegram_username = username
    user.save(update_fields=["telegram_id", "telegram_username"])
    roles = ", ".join(sorted(user.role_names)) or "—"
    return {"already": False, "name": user.full_name, "email": user.email, "roles": roles}


def user_for_chat(chat_id: str):
    """Bağlı kullanıcıyı döndürür; yoksa None (bot yalnız bağlı kişilere yanıt verir)."""
    from apps.accounts.models import User
    return User.objects.filter(telegram_id=str(chat_id)).first()


def unlink_chat(chat_id: str) -> bool:
    """Çıkış: telegram_id'yi temizler."""
    from apps.accounts.models import User
    user = User.objects.filter(telegram_id=str(chat_id)).first()
    if not user:
        return False
    user.telegram_id = ""
    user.save(update_fields=["telegram_id"])
    return True


def article_status(user, article_id: str) -> dict | None:
    """Kullanıcının YALNIZ kendi makalesinin durumunu döndürür (yetki kontrolü).

    `article_id` Submission pk'sıdır. Kullanıcı submitter ya da yazarsa görür.
    """
    from apps.submissions.models import Submission, SubmissionStatus, Stage
    try:
        sid = int(str(article_id).strip())
    except (ValueError, TypeError):
        return None
    qs = Submission.objects.filter(pk=sid)
    sub = qs.first()
    if not sub:
        return None
    is_owner = (sub.submitter_id == user.id)
    if not is_owner and user.email:
        is_owner = sub.publications.filter(authors__email__iexact=user.email).exists()
    if not is_owner:
        return None
    pub = sub.publications.order_by("-id").first()
    title = ""
    if pub:
        tr = pub.translations.filter(locale=pub.primary_locale).first() or pub.translations.first()
        title = tr.title if tr else ""
    return {
        "id": sid,
        "title": title or f"Submission #{sid}",
        "status": SubmissionStatus(sub.status).label if sub.status is not None else "—",
        "stage": Stage(sub.stage).label if sub.stage is not None else "—",
    }


def resolve_lang(user, telegram_lang: str = "") -> str:
    """Dil seçimi: kullanıcının tercih ettiği yerel, yoksa Telegram dili, yoksa en."""
    supported = {"en", "tr", "ru", "zh"}
    if user is not None:
        loc = (getattr(user, "preferred_locale", "") or "")[:2]
        if loc in supported:
            return loc
    tl = (telegram_lang or "")[:2]
    return tl if tl in supported else "en"


def quick_reply(user, text: str) -> str | None:
    """"1"/"2" hızlı hakem yanıtı — çekirdek servise köprü."""
    from apps.review.quick_response import handle_reply
    return handle_reply(user, text)
