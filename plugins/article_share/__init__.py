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
block plugin: makale sayfasına paylaş/atıf kutusu (HTML) enjekte eder.
'templates.article_extra' filtresine bağlanır.
"""
from django.utils.html import escape

from apps.plugins.base import Plugin, PluginCategory
from apps.plugins.hooks import hooks


class ArticleSharePlugin(Plugin):
    key = "article_share"
    name = "Article share box"
    category = PluginCategory.BLOCK
    description = "Adds share/cite links to the article page."

    def register(self):
        hooks.register("templates.article_extra", self.render, plugin=self)

    def render(self, html, *, publication, request):
        url = request.build_absolute_uri()
        t = publication.tr(publication.primary_locale)
        title = escape(t.title if t else "")
        box = (
            '<div style="border:1px solid var(--line);border-radius:.5rem;'
            'padding:1rem;background:#fffdf8">'
            '<div class="label" style="margin-bottom:.4rem">Share</div>'
            f'<a class="link" href="https://twitter.com/intent/tweet?text={title}&url={url}">X</a> · '
            f'<a class="link" href="https://www.linkedin.com/sharing/share-offsite/?url={url}">LinkedIn</a> · '
            f'<a class="link" href="mailto:?subject={title}&body={url}">Email</a>'
            '</div>'
        )
        return html + box


plugin = ArticleSharePlugin()
