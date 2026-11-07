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
oaiMetadata plugin: OAI-PMH'e yeni bir metadata formatı ('oai_cc') ekler.
'oai.formats' filtresine bağlanır; basit, gömülebilir bir kayıt üretir.
"""
from lxml import etree

from apps.plugins.base import Plugin, PluginCategory
from apps.plugins.hooks import hooks

NS = "https://ccjournal.example/oai_cc"


def _build(pub):
    root = etree.Element("{%s}record" % NS, nsmap={"cc": NS})
    t = pub.tr(pub.primary_locale)
    etree.SubElement(root, "{%s}title" % NS).text = t.title if t else ""
    if pub.doi_id:
        etree.SubElement(root, "{%s}doi" % NS).text = pub.doi.doi
    for a in pub.authors.all().order_by("seq"):
        etree.SubElement(root, "{%s}author" % NS).text = f"{a.given_name} {a.family_name}".strip()
    return root


class OaiSimplePlugin(Plugin):
    key = "oai_simple"
    name = "Simple OAI format (oai_cc)"
    category = PluginCategory.OAI_METADATA
    description = "Registers an extra OAI-PMH metadata format 'oai_cc'."

    def register(self):
        hooks.register("oai.formats", self.add_format, plugin=self)

    def add_format(self, formats):
        formats["oai_cc"] = {"namespace": NS, "schema": NS + ".xsd", "builder": _build}
        return formats


plugin = OaiSimplePlugin()
