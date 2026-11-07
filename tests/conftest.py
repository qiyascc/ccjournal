import pytest


@pytest.fixture(autouse=True)
def _clear_cache():
    """LocMem cache süreç-globaldir; testler arası sızmasın diye temizle."""
    from django.core.cache import cache
    cache.clear()
    yield


@pytest.fixture(scope="session", autouse=True)
def _disable_periodic_pulse():
    """Test istekleri periyodik daemon thread tetiklemesin (SQLite kilidi)."""
    from apps.tasks import middleware
    middleware.ENABLED = False
    yield
    middleware.ENABLED = True


@pytest.fixture(scope="session", autouse=True)
def _seed_email_templates(django_db_setup, django_db_blocker):
    """Varsayılan e-posta şablonları + roller test DB'de hep tam olsun.

    Prod'da post_migrate seed'ler; --reuse-db migrate'i atladığı için buradan
    tamamlanır (idempotent get_or_create).
    """
    with django_db_blocker.unblock():
        from apps.accounts.roles import seed_roles
        from apps.comms.models import EmailTemplate
        from apps.comms.seeding import seed
        from apps.core.locales import CONTENT_LOCALES
        seed_roles()
        seed(EmailTemplate, [c for c, _, _ in CONTENT_LOCALES])


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        email="editor@example.org", password="pw-long-enough-123", given_name="Edda")


@pytest.fixture
def journal(db):
    from apps.journals.models import Journal, JournalTranslation
    j = Journal.objects.create(path="testj", primary_locale="en",
                               supported_locales=["en"], enabled=True)
    JournalTranslation.objects.create(journal=j, locale="en", title="Test Journal")
    return j


@pytest.fixture
def section(journal):
    from apps.journals.models import Section, SectionTranslation
    s = Section.objects.create(journal=journal, primary_locale="en", abstracts_required=True)
    SectionTranslation.objects.create(section=s, locale="en", title="Articles")
    return s


@pytest.fixture
def make_issue(journal):
    from django.utils import timezone
    from apps.journals.models import Issue

    def _make(*, published=False, **kw):
        return Issue.objects.create(
            journal=journal, volume=1, number="1", year=2026, is_published=published,
            date_published=timezone.now() if published else None, **kw)
    return _make


@pytest.fixture
def issue_unpublished(make_issue):
    return make_issue(published=False)


@pytest.fixture
def issue_published(make_issue):
    return make_issue(published=True)


@pytest.fixture
def make_pub(journal, section, user):
    """Yayınlanabilir bir Publication (+ submission, çeviri, yazar, keyword, galley) üretir."""
    from apps.submissions.models import Submission
    from apps.publications.models import (
        Author, Galley, Keyword, Publication, PublicationTranslation,
    )

    def _make(*, issue=None, title="Hello World", abstract="An abstract.",
              approved_galley=True, sec=section):
        sub = Submission.objects.create(journal=journal, submitter=user, locale="en")
        pub = Publication.objects.create(
            submission=sub, primary_locale="en", section=sec, issue=issue)
        PublicationTranslation.objects.create(
            publication=pub, locale="en", title=title, abstract=abstract)
        Author.objects.create(publication=pub, given_name="Ada", family_name="Lovelace",
                              email="ada@example.org", credit_roles=["software"], seq=1)
        Keyword.objects.create(publication=pub, locale="en", term="computing", seq=1)
        if approved_galley:
            Galley.objects.create(publication=pub, label="PDF", is_approved=True)
        sub.current_publication = pub
        sub.save(update_fields=["current_publication"])
        return pub
    return _make
