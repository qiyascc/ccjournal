import pytest

pytestmark = pytest.mark.django_db

UA = "Mozilla/5.0 (pytest reader)"


@pytest.fixture
def published(journal, make_pub, issue_published):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="Counted Article")
    PublicationService.publish(pub)
    return pub


def _totals(pub):
    from apps.stats.services import StatsService
    return StatsService.totals(pub.submission)


def test_refresh_within_window_counts_once(client, published):
    url = f"/article/{published.submission_id}/"
    for _ in range(5):
        assert client.get(url, HTTP_USER_AGENT=UA).status_code == 200
    assert _totals(published)["abstract_views"] == 1


def test_after_window_counts_again(client, published):
    from django.core.cache import cache
    url = f"/article/{published.submission_id}/"
    client.get(url, HTTP_USER_AGENT=UA)
    cache.clear()
    client.get(url, HTTP_USER_AGENT=UA)
    assert _totals(published)["abstract_views"] == 2


def test_distinct_visitors_count_separately(client, published):
    url = f"/article/{published.submission_id}/"
    client.get(url, HTTP_USER_AGENT=UA)
    client.get(url, HTTP_USER_AGENT="Mozilla/5.0 (another reader)")
    assert _totals(published)["abstract_views"] == 2


def test_bots_not_counted(client, published):
    url = f"/article/{published.submission_id}/"
    client.get(url, HTTP_USER_AGENT="Googlebot/2.1")
    client.get(url)
    assert _totals(published)["abstract_views"] == 0


def test_staff_views_not_counted_by_default(client, published, django_user_model):
    staff = django_user_model.objects.create_user(
        email="staffreader@example.org", password="pw-long-enough-123",
        given_name="S", is_staff=True)
    client.force_login(staff)
    client.get(f"/article/{published.submission_id}/", HTTP_USER_AGENT=UA)
    assert _totals(published)["abstract_views"] == 0


def test_staff_views_counted_when_enabled(client, published, django_user_model):
    from constance.test import override_config
    staff = django_user_model.objects.create_user(
        email="staffreader2@example.org", password="pw-long-enough-123",
        given_name="S", is_staff=True)
    client.force_login(staff)
    with override_config(STATS_COUNT_STAFF_VIEWS=True):
        client.get(f"/article/{published.submission_id}/", HTTP_USER_AGENT=UA)
    assert _totals(published)["abstract_views"] == 1


def test_galley_and_abstract_filtered_independently(client, published):
    """Aynı ziyaretçinin özet VE galley görüntülemesi ayrı öğelerdir; ikisi de sayılır."""
    from apps.publications.models import Galley
    from apps.submissions.models import FileStage, SubmissionFile
    from django.core.files.uploadedfile import SimpleUploadedFile
    sf = SubmissionFile.objects.create(
        submission=published.submission,
        file=SimpleUploadedFile("a.pdf", b"%PDF-1.4"),
        original_filename="a.pdf", mimetype="application/pdf", file_size=8,
        file_stage=FileStage.PRODUCTION_READY)
    g = Galley.objects.filter(publication=published).first() or Galley.objects.create(
        publication=published, label="PDF", is_approved=True)
    g.file = sf
    g.is_approved = True
    g.save()
    client.get(f"/article/{published.submission_id}/", HTTP_USER_AGENT=UA)
    client.get(f"/article/{published.submission_id}/galley/{g.pk}/", HTTP_USER_AGENT=UA)
    client.get(f"/article/{published.submission_id}/galley/{g.pk}/", HTTP_USER_AGENT=UA)
    t = _totals(published)
    assert t["abstract_views"] == 1
    assert t["galley_views"] == 1
