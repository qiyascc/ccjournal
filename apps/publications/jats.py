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

"""JATS XML galley üretimi.

`apps.metadata.serializers.to_jats` (OAI'de de kullanılan) makale JATS'ını
üretir; burada aynı XML bir **galley** dosyası olarak kaydedilir ve makale
sayfasından `/article/<pk>/jats.xml` ile indirilebilir. Ön yüz (front matter)
tam metadata içerir — PubMed/DOAJ/koruma sistemlerinin harmanladığı bölüm
budur. Tam-metin gövdenin JATS <body>'e dönüşümü (HTML→JATS) yol haritasında.
"""
from __future__ import annotations

from django.core.files.base import ContentFile


def jats_bytes(publication) -> bytes:
    from lxml import etree

    from apps.metadata.serializers import to_jats
    el = to_jats(publication)
    return etree.tostring(el, xml_declaration=True, encoding="UTF-8",
                          pretty_print=True)


def generate_jats_galley(publication, *, label="XML", approve=True):
    """JATS XML galley üretir/yeniler; Galley döndürür."""
    from apps.submissions.models import FileStage, SubmissionFile

    from .models import Galley

    data = jats_bytes(publication)
    sub = publication.submission
    fname = f"article-{sub.pk}-jats.xml"
    sf = SubmissionFile.objects.create(
        submission=sub, original_filename=fname, mimetype="application/xml",
        file_stage=FileStage.PRODUCTION_READY, file_size=len(data))
    sf.file.save(f"galley/{publication.pk}-{fname}", ContentFile(data), save=True)

    galley = (publication.galleys.filter(label=label, remote_url="")
              .order_by("seq").first())
    if galley:
        galley.file = sf
        galley.is_approved = approve
        galley.save(update_fields=["file", "is_approved"])
    else:
        galley = Galley.objects.create(
            publication=publication, label=label, file=sf, is_approved=approve,
            seq=(publication.galleys.count() + 1) * 1.0)
    return galley
