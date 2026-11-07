#!/usr/bin/env python3
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

"""CC Journal — Telegram bot sidecar (python-telegram-bot, polling).

Plugin etkinleştirilince Django bu süreci başlatır. Aynı SQLite'a django.setup()
ile bağlanır; gelen komutları logic.py üzerinden işler. Bildirim GÖNDERME işi bu
süreçte değil — onu Django kanalı doğrudan Telegram API'siyle yapar.

Bot yalnız bağlı (telegram_id'si olan) kullanıcılara yanıt verir; /start ve token
mesajı istisnadır (bunlar bağlanmayı sağlar).
"""
import os
import sys
import django
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from asgiref.sync import sync_to_async  # noqa: E402
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  # noqa: E402
from telegram.constants import ParseMode  # noqa: E402
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,  # noqa: E402
                          CallbackQueryHandler, ContextTypes, filters)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402
from i18n import t  # noqa: E402


def _journal_name() -> str:
    try:
        from apps.journals.models import Journal
        j = Journal.objects.first()
        if j:
            tr = j.translations.filter(locale=j.primary_locale).first() or j.translations.first()
            return tr.title if tr else "CC Journal"
    except Exception:
        pass
    return "CC Journal"


async def _lang(chat_id, tg_lang):
    user = await sync_to_async(logic.user_for_chat)(chat_id)
    return logic.resolve_lang(user, tg_lang), user


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    tg_lang = update.effective_user.language_code if update.effective_user else "en"
    lang, user = await _lang(chat_id, tg_lang)
    if ctx.args:
        await _try_link(update, ctx, ctx.args[0].strip(), lang)
        return
    journal = await sync_to_async(_journal_name)()
    await update.message.reply_text(t(lang, "start_intro", journal=journal),
                                    parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang, user = await _lang(chat_id, update.effective_user.language_code)
    if user is None:
        await update.message.reply_text(t(lang, "not_linked"), parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(t(lang, "help"), parse_mode=ParseMode.MARKDOWN)


async def _try_link(update, ctx, token, lang):
    chat_id = update.effective_chat.id
    uname = update.effective_user.username if update.effective_user else ""
    info = await sync_to_async(logic.link_account_by_token)(token, chat_id, uname or "")
    if info is None:
        await update.message.reply_text(t(lang, "bad_token"), parse_mode=ParseMode.MARKDOWN)
    elif info.get("already"):
        await update.message.reply_text(t(lang, "already_linked", name=info["name"]),
                                        parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            t(lang, "linked", name=info["name"], email=info["email"], roles=info["roles"]),
            parse_mode=ParseMode.MARKDOWN)


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Düz metin: bağlı değilse token; bağlıysa önce hızlı hakem yanıtı (1/2)."""
    chat_id = update.effective_chat.id
    lang, user = await _lang(chat_id, update.effective_user.language_code)
    text = (update.message.text or "").strip()
    if user is None:
        await _try_link(update, ctx, text, lang)
        return
    reply = await logic_quick_reply(user, text)
    if reply:
        await update.message.reply_text(reply)
        return
    await update.message.reply_text(t(lang, "help"), parse_mode=ParseMode.MARKDOWN)


async def logic_quick_reply(user, text):
    from asgiref.sync import sync_to_async

    from logic import quick_reply
    return await sync_to_async(quick_reply)(user, text)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang, user = await _lang(chat_id, update.effective_user.language_code)
    if user is None:
        await update.message.reply_text(t(lang, "not_linked"), parse_mode=ParseMode.MARKDOWN)
        return
    if not ctx.args:
        await update.message.reply_text(t(lang, "status_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    aid = ctx.args[0]
    res = await sync_to_async(logic.article_status)(user, aid)
    if res is None:
        await update.message.reply_text(t(lang, "status_not_found", id=aid),
                                        parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(t(lang, "status_line", **res),
                                        parse_mode=ParseMode.MARKDOWN)


async def cmd_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang, user = await _lang(chat_id, update.effective_user.language_code)
    if user is None:
        await update.message.reply_text(t(lang, "not_linked"), parse_mode=ParseMode.MARKDOWN)
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "logout_yes"), callback_data="logout:yes"),
        InlineKeyboardButton(t(lang, "logout_no"), callback_data="logout:no"),
    ]])
    await update.message.reply_text(t(lang, "logout_confirm"), reply_markup=kb)


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat.id
    lang, user = await _lang(chat_id, q.from_user.language_code if q.from_user else "en")
    await q.answer()
    if q.data == "logout:yes":
        await sync_to_async(logic.unlink_chat)(chat_id)
        await q.edit_message_text(t(lang, "logout_done"))
    else:
        await q.edit_message_text(t(lang, "logout_cancel"))


def main():
    token = os.environ.get("TG_TOKEN", "")
    if not token:
        print("TG_TOKEN missing", file=sys.stderr)
        sys.exit(1)
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^logout:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
