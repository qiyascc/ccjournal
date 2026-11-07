import pytest
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def test_publish_scheduled_when_issue_unpublished(make_pub, issue_unpublished):
    from apps.publications.models import PublicationStatus
    from apps.publications.services import PublicationService
    from apps.submissions.models import SubmissionStatus

    pub = make_pub(issue=issue_unpublished)
    PublicationService.publish(pub)
    pub.refresh_from_db()
    assert pub.status == PublicationStatus.SCHEDULED
    assert pub.submission.status == SubmissionStatus.SCHEDULED


def test_publish_published_when_issue_published(make_pub, issue_published):
    from apps.publications.models import PublicationStatus
    from apps.publications.services import PublicationService
    from apps.submissions.models import SubmissionStatus

    pub = make_pub(issue=issue_published)
    PublicationService.publish(pub)
    pub.refresh_from_db()
    assert pub.status == PublicationStatus.PUBLISHED
    assert pub.date_published is not None
    assert pub.submission.status == SubmissionStatus.PUBLISHED
    assert pub.submission.current_publication_id == pub.id


def test_validate_publish_requires_issue(make_pub):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=None)
    with pytest.raises(ValidationError):
        PublicationService.validate_publish(pub)


def test_validate_publish_requires_approved_galley(make_pub, issue_published):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, approved_galley=False)
    with pytest.raises(ValidationError):
        PublicationService.validate_publish(pub)


def test_validate_publish_requires_abstract_when_section_demands(make_pub, issue_published):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, abstract="")
    with pytest.raises(ValidationError):
        PublicationService.validate_publish(pub)


def test_publish_force_skips_validation(make_pub):
    from apps.publications.models import PublicationStatus
    from apps.publications.services import PublicationService
    pub = make_pub(issue=None, approved_galley=False)
    PublicationService.publish(pub, force=True)
    pub.refresh_from_db()
    assert pub.status == PublicationStatus.SCHEDULED


def test_issue_publish_cascades_scheduled_to_published(make_pub, issue_unpublished):
    from apps.publications.models import PublicationStatus
    from apps.publications.services import IssueService, PublicationService
    from apps.submissions.models import SubmissionStatus

    pub = make_pub(issue=issue_unpublished)
    PublicationService.publish(pub)
    assert pub.status == PublicationStatus.SCHEDULED

    IssueService.publish_issue(issue_unpublished)
    pub.refresh_from_db()
    assert pub.status == PublicationStatus.PUBLISHED
    assert pub.submission.status == SubmissionStatus.PUBLISHED


def test_create_version_minor_deep_clone(make_pub, issue_published):
    from apps.publications.models import PublicationStatus
    from apps.publications.services import PublicationService

    pub = make_pub(issue=issue_published)
    v2 = PublicationService.create_version(pub, minor=True)

    assert (v2.version_major, v2.version_minor) == (1, 1)
    assert v2.source_publication_id == pub.id
    assert v2.issue_id is None
    assert v2.status == PublicationStatus.QUEUED
    assert v2.translations.count() == 1
    assert v2.authors.count() == 1
    assert v2.keywords.count() == 1
    assert v2.authors.first().id != pub.authors.first().id
    assert v2.authors.first().credit_roles == ["software"]


def test_create_version_major_resets_minor(make_pub):
    from apps.publications.services import PublicationService
    pub = make_pub()
    v = PublicationService.create_version(pub, minor=False)
    assert (v.version_major, v.version_minor) == (2, 0)


def test_doi_minted_on_publish_when_enabled(make_pub, issue_published, journal):
    from apps.publications.services import PublicationService
    journal.enable_doi = True
    journal.doi_prefix = "10.1234"
    journal.save(update_fields=["enable_doi", "doi_prefix"])

    pub = make_pub(issue=issue_published)
    PublicationService.publish(pub)
    pub.refresh_from_db()
    assert pub.doi_id is not None
    assert pub.doi.doi.startswith("10.1234/")
    assert pub.galleys.first().doi_id is not None


def test_no_doi_when_disabled(make_pub, issue_published):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published)
    PublicationService.publish(pub)
    pub.refresh_from_db()
    assert pub.doi_id is None


def test_unpublish_creates_tombstone(make_pub, issue_published):
    from apps.metadata.models import Tombstone
    from apps.publications.models import PublicationStatus
    from apps.publications.services import PublicationService

    pub = make_pub(issue=issue_published)
    PublicationService.publish(pub)
    PublicationService.unpublish(pub)
    pub.refresh_from_db()

    assert pub.status == PublicationStatus.QUEUED
    assert Tombstone.objects.filter(submission=pub.submission).exists()
