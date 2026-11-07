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

"""WhatsApp notifications plugin (Node.js + Baileys).

Etkinleştirildiğinde bir Node.js sidecar (Baileys) başlatır. Admin'deki plugin
ayrıntı sayfasında bir QR kod gösterilir; telefonla tarandığında oturum kalıcı olur
ve mesajlaşma başlar — sunucudan ayrıca bir başlatma gerekmez.

Bildirimler e-posta sistemiyle aynı şablonları kullanır: her e-posta gönderildiğinde
`notification.send` action'ı tetiklenir; bu plugin, alıcı kullanıcıların WhatsApp
numaralarına aynı içeriği iletir.

Plugin devre dışı bırakılınca sidecar durdurulur ve `User.whatsapp_number` alanı
admin'de gizlenir (veri DB'de korunur; tekrar açılınca görünür).
"""
from apps.plugins.base import Plugin, PluginCategory


class WhatsAppPlugin(Plugin):
    key = "whatsapp"
    name = "WhatsApp notifications"
    version = "1.0.0"
    category = PluginCategory.GENERIC
    description = ("Delivers notifications over WhatsApp (Node.js + Baileys). "
                   "Scan a QR in the plugin page; uses email templates as content.")
    author = "Qiyas CC"

    def register(self):
        from apps.comms.channels import registry as channel_registry
        from .channel import WhatsAppChannel
        channel_registry.register(WhatsAppChannel())

    def on_enable(self):
        from .client import start
        start()

    def on_disable(self):
        from .client import stop
        stop()


plugin = WhatsAppPlugin()
