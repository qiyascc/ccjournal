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
Bilimsel yayıncılık kimlik (identifier) altyapısı.

OJS bunları gevşek `setting_name='pub-id::doi'` gibi tutar. Biz tipli, doğrulamalı,
yeniden kullanılabilir alanlar veriyoruz. Bu, Crossref/DataCite/OpenAIRE/ORCID
entegrasyonlarını ve metadata kalitesini ciddi şekilde yükseltir.
"""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.db import models


ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
ROR_RE = re.compile(r"^https?://ror\.org/0[a-hj-km-np-z0-9]{8}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$")


def validate_orcid(value: str) -> None:
    if not ORCID_RE.match(value or ""):
        raise ValidationError("Geçersiz ORCID (örn. 0000-0002-1825-0097).")


def validate_ror(value: str) -> None:
    if value and not ROR_RE.match(value):
        raise ValidationError("Geçersiz ROR URI (örn. https://ror.org/05dxps055).")


def validate_doi(value: str) -> None:
    if value and not DOI_RE.match(value):
        raise ValidationError("Geçersiz DOI (örn. 10.1234/abcd.5678).")


def validate_issn(value: str) -> None:
    if value and not ISSN_RE.match(value):
        raise ValidationError("Geçersiz ISSN (örn. 1234-5678).")


class Doi(models.Model):
    """
    DOI'yi ayrı bir varlık olarak modelliyoruz: hem dergiye, hem sayıya, hem
    yayına, hem galley'e atanabilir ve kayıt (deposit) durumu izlenebilir.
    OJS'te de DOI ayrı bir tablodur; biz durum makinesini netleştiriyoruz.
    """

    class Status(models.IntegerChoices):
        UNREGISTERED = 1, "Unregistered"
        SUBMITTED = 2, "Submitted"
        REGISTERED = 3, "Registered"
        ERROR = 4, "Error"
        STALE = 5, "Stale (metadata changed)"

    class Agency(models.TextChoices):
        CROSSREF = "crossref", "Crossref"
        DATACITE = "datacite", "DataCite"
        MANUAL = "manual", "Manual"

    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.CASCADE, related_name="dois"
    )
    doi = models.CharField(max_length=255, unique=True, validators=[validate_doi])
    status = models.IntegerField(choices=Status.choices, default=Status.UNREGISTERED)
    agency = models.CharField(max_length=20, choices=Agency.choices, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    last_response = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return self.doi

    @property
    def url(self) -> str:
        return f"https://doi.org/{self.doi}"
