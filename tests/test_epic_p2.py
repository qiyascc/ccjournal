import pytest
from django.core import mail

pytestmark = pytest.mark.django_db


# --- E-posta doğrulama (config-gated) ---------------------------------------

def test_registration_default_no_verification(client, journal):
    resp = client.post("/accounts/register/", {
        "email": "plain@example.org", "given_name": "P", "family_name": "",
        "affiliation": "", "orcid": "", "password": "a-strong-pass-99"})
    assert resp.status_code == 302 and resp.url == "/dashboard/"


def test_registration_with_verification_flow(client, journal, django_user_model):
    from constance.test import override_config
    with override_config(REQUIRE_EMAIL_VERIFICATION=True):
        resp = client.post("/accounts/register/", {
            "email": "verifyme@example.org", "given_name": "V", "family_name": "",
            "affiliation": "", "orcid": "", "password": "a-strong-pass-99"})
        assert resp.status_code == 200
        assert b"Check your email" in resp.content
        user = django_user_model.objects.get(email="verifyme@example.org")
        assert user.is_active is False
        body = mail.outbox[-1].body
        assert "/accounts/verify/" in body
        token = body.split("/accounts/verify/")[1].split("/")[0]
        resp = client.get(f"/accounts/verify/{token}/")
        assert resp.status_code == 302 and resp.url == "/dashboard/"
        user.refresh_from_db()
        assert user.is_active is True


def test_verify_bad_token_404(client, journal):
    assert client.get("/accounts/verify/garbage/").status_code == 404


# --- Issue galley (tam sayı PDF'i) --------------------------------------------

def test_issue_galley_download_and_paywall(client, journal, issue_published,
                                           django_user_model):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from waffle.testutils import override_switch
    from apps.journals.models import Issue
    issue = issue_published
    assert client.get(f"/issue/{issue.pk}/galley/").status_code == 404  # dosya yok
    issue.galley_file = SimpleUploadedFile("full.pdf", b"%PDF-1.4 issue")
    issue.save(update_fields=["galley_file"])
    resp = client.get(f"/issue/{issue.pk}/galley/")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    # abonelik anahtarı açık + subscription-only sayı → anonim 403
    issue.access = Issue.Access.SUBSCRIPTION
    issue.save(update_fields=["access"])
    with override_switch("subscriptions", active=True):
        assert client.get(f"/issue/{issue.pk}/galley/").status_code == 403
        staff = django_user_model.objects.create_user(
            email="ig-staff@example.org", password="pw-long-enough-123",
            given_name="S", is_staff=True)
        client.force_login(staff)
        assert client.get(f"/issue/{issue.pk}/galley/").status_code == 200


def test_issue_page_shows_galley_link(client, journal, issue_published):
    from django.core.files.uploadedfile import SimpleUploadedFile
    issue_published.galley_file = SimpleUploadedFile("full.pdf", b"%PDF-1.4")
    issue_published.save(update_fields=["galley_file"])
    html = client.get(f"/issue/{issue_published.pk}/").content.decode()
    assert f"/issue/{issue_published.pk}/galley/" in html


# --- DOAJ export ----------------------------------------------------------------

def test_doaj_export_staff_only_and_schema(client, journal, make_pub,
                                           issue_published, django_user_model):
    import json
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="DOAJ Article")
    PublicationService.publish(pub)
    assert client.get("/export/doaj").status_code == 403
    staff = django_user_model.objects.create_user(
        email="doaj@example.org", password="pw-long-enough-123",
        given_name="D", is_staff=True)
    client.force_login(staff)
    resp = client.get("/export/doaj")
    assert resp.status_code == 200
    data = json.loads(resp.content)
    bib = next(d["bibjson"] for d in data if d["bibjson"]["title"] == "DOAJ Article")
    assert bib["author"][0]["name"] == "Ada Lovelace"
    assert bib["journal"]["title"] == "Test Journal"
    assert bib["link"][0]["type"] == "fulltext"


# --- Highlights -------------------------------------------------------------------

def test_highlights_on_home(client, journal):
    from apps.journals.models import Highlight, HighlightTranslation
    h = Highlight.objects.create(journal=journal, primary_locale="en",
                                 url="/announcements/", seq=1)
    HighlightTranslation.objects.create(highlight=h, locale="en",
                                        title="Call for Papers 2027",
                                        blurb="Special issue on X.", cta="Submit now")
    html = client.get("/").content.decode()
    assert "Call for Papers 2027" in html and "Submit now" in html
    h.is_active = False
    h.save(update_fields=["is_active"])
    from django.core.cache import cache
    cache.clear()
    assert "Call for Papers 2027" not in client.get("/").content.decode()


# --- Retraction banner ---------------------------------------------------------------

def test_retraction_banner_on_article(client, journal, make_pub, issue_published):
    from django.utils import timezone
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="Retract Me")
    PublicationService.publish(pub)
    url = f"/article/{pub.submission_id}/"
    assert "RETRACTED" not in client.get(url).content.decode()
    pub.retracted_at = timezone.localdate()
    pub.retraction_note = "Data fabrication was identified."
    pub.save(update_fields=["retracted_at", "retraction_note"])
    html = client.get(url).content.decode()
    assert "RETRACTED" in html and "Data fabrication" in html


# --- Dosya yöneticisinden galley oluşturma ---------------------------------------------

def test_make_galley_from_production_ready(client, journal, make_pub, django_user_model):
    from django.contrib.auth.models import Group
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.submissions.models import FileStage, SubmissionFile
    pub = make_pub(approved_galley=False)
    sub = pub.submission
    sf = SubmissionFile.objects.create(
        submission=sub, file=SimpleUploadedFile("final.pdf", b"%PDF-1.4 final"),
        original_filename="final.pdf", mimetype="application/pdf", file_size=14,
        file_stage=FileStage.PRODUCTION_READY)
    editor = django_user_model.objects.create_user(
        email="mg-ed@example.org", password="pw-long-enough-123",
        given_name="E", is_staff=True)
    grp, _ = Group.objects.get_or_create(name="Editor")
    editor.groups.add(grp)
    client.force_login(editor)
    html = client.get(f"/manage/files/{sub.pk}/").content.decode()
    assert "Create galley" in html
    resp = client.post(f"/manage/files/{sub.pk}/",
                       {"action": "make_galley", "file_id": sf.pk})
    assert resp.status_code == 302
    g = pub.galleys.get()
    assert g.label == "PDF" and g.is_approved and g.file_id == sf.pk
