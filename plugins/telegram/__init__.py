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

"""Telegram notifications plugin (python-telegram-bot).

Etkinleştirilince admin'de bot token'ı girilir; polling botu otomatik başlar.
Kullanıcılar profillerindeki “Start telegram bot” bağlantısı/anahtarıyla hesaplarını
bağlar. Bot yalnız bağlı kişilere yanıt verir; /start, /help, /status <id>, /logout
komutlarını 4 dilde (tr/en/ru/zh) destekler. Bildirimler e-posta şablonlarından
beslenir ve Telegram bir bildirim kanalı olarak çalışır (e-postadan bağımsız).
"""
from apps.plugins.base import Plugin, PluginCategory


class TelegramPlugin(Plugin):
    key = "telegram"
    name = "Telegram notifications"
    version = "1.0.0"
    category = PluginCategory.GENERIC
    description = ("Telegram bot notifications + author self-service "
                   "(/status, /logout) in 4 languages. Uses email templates as content.")
    author = "Qiyas CC"

    def register(self):
        from apps.comms.channels import registry as channel_registry
        from .channel import TelegramChannel
        channel_registry.register(TelegramChannel())

    def on_enable(self):
        from .client import start
        start()

    def on_disable(self):
        from .client import stop
        stop()


plugin = TelegramPlugin()
