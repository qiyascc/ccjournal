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
Yayın iş kuralları (servis katmanı).

Tüm "custom" davranışın toplandığı yer. View/admin bunları ÇAĞIRIR; mantık burada
durur. OJS karşılıkları: Repository::version(), Repository::setStatusOnPublish(),
createDois(), tombstone üretimi.

Özelleştirme kancaları (CUSTOM):
  * DOI_SUFFIX_BUILDER  -> DOI sonek şeması
  * PublicationService.validate_publish -> yayın ön-koşulları
"""
from __future__ import annotations

from collections.abc import Callable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Doi
from apps.submissions.models import SubmissionStatus
from .models import (
    Author, Citation, Funding, Galley, Keyword, Publication, PublicationStatus,
    PublicationTranslation, Subject,
)


def default_doi_suffix(publication: Publication) -> str:
    """CUSTOM: DOI sonek şeması. Örn. cc.v1i2.42  veya  cc.42.v2 (yeni sürüm)."""
    sub = publication.submission
    parts = [sub.journal.path]
    iss = publication.issue
    if iss and iss.volume:
        parts.append(f"v{iss.volume}" + (f"i{iss.number}" if iss.number else ""))
    parts.append(str(sub.id))
    if (publication.version_major, publication.version_minor) != (1, 0):
        parts.append(f"v{publication.version_major}-{publication.version_minor}")
    return ".".join(parts)


DOI_SUFFIX_BUILDER: Callable[[Publication], str] = default_doi_suffix


class DoiService:
    @staticmethod
    @transaction.atomic
    def mint_for_publication(publication: Publication) -> Doi | None:
        journal = publication.submission.journal
        if not (journal.enable_doi and journal.doi_prefix):
            return None
        if publication.doi_id:
            return publication.doi
        from apps.plugins.hooks import hooks
        suffix = hooks.apply_filters("doi.suffix", DOI_SUFFIX_BUILDER(publication),
                                     publication=publication)
        doi_str = f"{journal.doi_prefix}/{suffix}"
        doi = Doi.objects.create(journal=journal, doi=doi_str)
        publication.doi = doi
        publication.save(update_fields=["doi"])
        for i, galley in enumerate(publication.galleys.all(), start=1):
            if not galley.doi_id:
                galley.doi = Doi.objects.create(journal=journal, doi=f"{doi_str}.g{i}")
                galley.save(update_fields=["doi"])
        return doi


class PublicationService:

    @staticmethod
    @transaction.atomic
    def create_version(publication: Publication, *, minor: bool = True, stage=None) -> Publication:
        """
        Bir yayını yeni bir sürüme klonlar (OJS Repository::version()).
        Tüm metadata (çeviri, yazar, anahtar kelime, konu, kaynakça, fon, galley)
        derin kopyalanır. Yeni sürüm taslak (QUEUED) ve sayısız başlar.
        """
        new = Publication.objects.create(
            submission=publication.submission,
            primary_locale=publication.primary_locale,
            section=publication.section,
            issue=None,
            seq=publication.seq,
            pages=publication.pages,
            version_stage=stage or publication.version_stage,
            version_major=publication.version_major + (0 if minor else 1),
            version_minor=(publication.version_minor + 1) if minor else 0,
            status=PublicationStatus.QUEUED,
            license_url=publication.license_url,
            copyright_holder=publication.copyright_holder,
            copyright_year=publication.copyright_year,
            source_publication=publication,
        )

        for t in publication.translations.all():
            PublicationTranslation.objects.create(
                publication=new, locale=t.locale, prefix=t.prefix, title=t.title,
                subtitle=t.subtitle, abstract=t.abstract,
                plain_language_summary=t.plain_language_summary,
                coverage=t.coverage, rights=t.rights,
            )

        author_map: dict[int, Author] = {}
        for a in publication.authors.all():
            author_map[a.id] = Author.objects.create(
                publication=new, given_name=a.given_name, family_name=a.family_name,
                email=a.email, orcid=a.orcid, affiliation=a.affiliation,
                affiliation_ror=a.affiliation_ror, country=a.country,
                biography=a.biography, credit_roles=list(a.credit_roles),
                seq=a.seq, include_in_browse=a.include_in_browse,
            )
        if publication.primary_contact_id in author_map:
            new.primary_contact = author_map[publication.primary_contact_id]
            new.save(update_fields=["primary_contact"])

        Keyword.objects.bulk_create([
            Keyword(publication=new, locale=k.locale, term=k.term, seq=k.seq)
            for k in publication.keywords.all()
        ])
        Subject.objects.bulk_create([
            Subject(publication=new, locale=s.locale, term=s.term)
            for s in publication.subjects.all()
        ])
        Citation.objects.bulk_create([
            Citation(publication=new, seq=c.seq, raw=c.raw, doi=c.doi, structured=c.structured)
            for c in publication.citations.all()
        ])
        Funding.objects.bulk_create([
            Funding(publication=new, funder_name=f.funder_name, funder_id=f.funder_id,
                    award_numbers=list(f.award_numbers))
            for f in publication.funders.all()
        ])
        for g in publication.galleys.all():
            Galley.objects.create(
                publication=new, locale=g.locale, label=g.label, file=g.file,
                remote_url=g.remote_url, is_approved=g.is_approved,
                url_path=g.url_path, seq=g.seq,
            )
        return new

    @staticmethod
    def validate_publish(publication: Publication, *, require_galley: bool = True) -> None:
        """CUSTOM: yayın ön-koşulları. Hata varsa ValidationError fırlatır."""
        errors: list[str] = []
        if not publication.issue_id:
            errors.append("Assign the article to an issue before publishing. "
                          "In OJS-style flow an article is published as part of an issue.")
        if not publication.section_id:
            errors.append("A section is required before publishing.")
        primary = publication.primary_locale
        if not publication.translations.filter(locale=primary).exclude(title="").exists():
            errors.append(f"A title in the primary locale ({primary}) is required.")
        if publication.section_id and publication.section.abstracts_required:
            if not publication.translations.exclude(abstract="").exists():
                errors.append("An abstract is required for this section.")
        if require_galley and not publication.galleys.filter(is_approved=True).exists():
            errors.append("At least one approved galley is required.")
        if errors:
            raise ValidationError(errors)

    @staticmethod
    @transaction.atomic
    def publish(publication: Publication, *, issue=None, force: bool = False) -> Publication:
        """
        Yayınlama durum makinesi (OJS setStatusOnPublish):
          * makale MUTLAKA bir sayıya bağlı olmalı (validate_publish zorlar)
          * sayı yayımlanmış    -> PUBLISHED (hemen)
          * sayı yayımlanmamış  -> SCHEDULED (sayı yayımlanınca PUBLISHED'a döner)

        Yani makale tek başına "publish" edilemez; sayının bir parçası olarak yayımlanır.
        """
        if issue is not None:
            publication.issue = issue
        if not force:
            PublicationService.validate_publish(publication)
        iss = publication.issue

        if iss is not None and iss.is_published:
            publication.status = PublicationStatus.PUBLISHED
            publication.date_published = timezone.localdate()
        else:
            publication.status = PublicationStatus.SCHEDULED
        publication.save(update_fields=["issue", "status", "date_published"])

        DoiService.mint_for_publication(publication)

        sub = publication.submission
        sub.current_publication = publication
        sub.status = (
            SubmissionStatus.PUBLISHED
            if publication.status == PublicationStatus.PUBLISHED
            else SubmissionStatus.SCHEDULED
        )
        sub.save(update_fields=["current_publication", "status", "date_status_modified"])
        if publication.status == PublicationStatus.PUBLISHED:
            from apps.comms.services import publication_published
            from apps.plugins.hooks import hooks
            from apps.tasks.queue import enqueue_or_run
            enqueue_or_run("apps.search.tasks.reindex", sub.id)
            hooks.do_action("publication.published", publication=publication)
            publication_published.send(sender=Publication, publication=publication)
        from apps.core.models import SiteState
        SiteState.bump()
        return publication

    @staticmethod
    @transaction.atomic
    def unpublish(publication: Publication) -> Publication:
        """Yayından çeker; yayımlanmıştıysa OAI için tombstone bırakır."""
        was_published = publication.status == PublicationStatus.PUBLISHED
        publication.status = PublicationStatus.QUEUED
        publication.save(update_fields=["status"])

        sub = publication.submission
        if was_published:
            from apps.metadata.models import Tombstone
            from apps.metadata.oai import oai_identifier
            t = (publication.translations.filter(locale=publication.primary_locale).first()
                 or publication.translations.first())
            sec_id = publication.section_id
            Tombstone.objects.create(
                journal=sub.journal, submission=sub,
                oai_identifier=oai_identifier(sub.journal.path, sub.id),
                set_spec=(f"sec:{sec_id}" if sec_id else ""),
                set_name=(publication.section.tr_value("title") if sec_id else ""),
                title_snapshot=(t.title if t else ""),
                doi_snapshot=(publication.doi.doi if publication.doi_id else ""),
            )
        sub.status = SubmissionStatus.QUEUED
        sub.save(update_fields=["status", "date_status_modified"])
        from apps.search.services import SearchIndex
        SearchIndex.remove(sub.id)
        from apps.core.models import SiteState
        SiteState.bump()
        return publication


class IssueService:
    @staticmethod
    @transaction.atomic
    def publish_issue(issue, *, notify_readers: bool = True):
        first_publish = not issue.is_published
        issue.is_published = True
        if not issue.date_published:
            issue.date_published = timezone.now()
        issue.save(update_fields=["is_published", "date_published"])
        for pub in issue.publications.filter(status=PublicationStatus.SCHEDULED):
            pub.status = PublicationStatus.PUBLISHED
            pub.date_published = timezone.localdate()
            pub.save(update_fields=["status", "date_published"])
            sub = pub.submission
            sub.status = SubmissionStatus.PUBLISHED
            sub.save(update_fields=["status", "date_status_modified"])
            from apps.comms.services import publication_published
            from apps.tasks.queue import enqueue_or_run
            enqueue_or_run("apps.search.tasks.reindex", sub.id)
            publication_published.send(sender=Publication, publication=pub)
        if notify_readers and first_publish:
            from apps.tasks.queue import enqueue_or_run
            transaction.on_commit(
                lambda: enqueue_or_run("apps.comms.tasks.notify_readers_new_issue", issue.id))
        from apps.core.models import SiteState
        SiteState.bump()
        return issue

    @staticmethod
    @transaction.atomic
    def unpublish_issue(issue):
        issue.is_published = False
        issue.save(update_fields=["is_published"])
        for pub in issue.publications.filter(status=PublicationStatus.PUBLISHED):
            pub.status = PublicationStatus.SCHEDULED
            pub.save(update_fields=["status"])
        from apps.core.models import SiteState
        SiteState.bump()
        return issue
