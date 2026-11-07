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
generic plugin: her giden e-postanın sonuna dergi imzası ekler.
'email.body' filtresine bağlanır. İmza metni plugin ayarından okunur.
"""
from apps.plugins.base import Plugin, PluginCategory
from apps.plugins.hooks import hooks


class EmailSignaturePlugin(Plugin):
    key = "email_signature"
    name = "Email signature"
    category = PluginCategory.GENERIC
    description = "Appends a journal signature to every outgoing email."

    def register(self):
        hooks.register("email.body", self.append, plugin=self)

    def append(self, body, *, key, journal):
        sig = self.get_setting("signature",
                               default="—\nThe Editorial Office")
        return f"{body}\n\n{sig}"


plugin = EmailSignaturePlugin()
