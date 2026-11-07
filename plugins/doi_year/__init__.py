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
pubId plugin: DOI soneğini yıl-tabanlı şemaya çevirir -> {prefix}/{year}.{submission_id}
'doi.suffix' filtresine bağlanır.
"""
from apps.plugins.base import Plugin, PluginCategory
from apps.plugins.hooks import hooks


class DoiYearPlugin(Plugin):
    key = "doi_year"
    name = "Year-based DOI suffix"
    category = PluginCategory.PUB_ID
    description = "DOI suffix as {year}.{submission_id}."

    def register(self):
        hooks.register("doi.suffix", self.suffix, plugin=self)

    def suffix(self, current, *, publication):
        year = publication.date_published.year if publication.date_published else "0000"
        return f"{year}.{publication.submission_id}"


plugin = DoiYearPlugin()
