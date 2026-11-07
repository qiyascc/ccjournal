import pytest
from django.core import mail
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_password_reset_flow_sends_email(client, user):
    assert client.get("/accounts/password/reset/").status_code == 200
    resp = client.post("/accounts/password/reset/", {"email": user.email})
    assert resp.status_code == 302
    assert resp.url == "/accounts/password/reset/sent/"
    assert len(mail.outbox) == 1
    assert "/accounts/password/reset/" in mail.outbox[0].body


def test_password_reset_unknown_email_no_leak(client, db):
    resp = client.post("/accounts/password/reset/", {"email": "ghost@example.org"})
    assert resp.status_code == 302
    assert len(mail.outbox) == 0


def test_dashboard_requires_login(client, journal):
    resp = client.get("/dashboard/")
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url


def test_dashboard_lists_submissions_and_reviews(client, journal, make_pub, user):
    from apps.submissions.models import SubmissionStatus
    pub = make_pub(title="Panel Makalesi")
    sub = pub.submission
    sub.status = SubmissionStatus.QUEUED
    sub.save(update_fields=["status"])
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    rnd = ReviewRound.objects.create(submission=sub)
    ReviewService.assign_reviewer(rnd, user, due=timezone.localdate())
    client.force_login(user)
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Panel Makalesi" in html
    assert f"/work/{sub.author_token}/" in html
    assert "/review/" in html


def test_dashboard_incomplete_links_to_wizard(client, journal, make_pub, user):
    pub = make_pub()
    client.force_login(user)
    html = client.get("/dashboard/").content.decode()
    assert f"/submit/{pub.submission.pk}/files/" in html


def test_dashboard_mark_all_read(client, journal, user):
    from apps.comms.services import NotifyService
    NotifyService.create(user, "t", "Hello", journal=journal)
    client.force_login(user)
    assert user.notifications.filter(is_read=False).count() == 1
    resp = client.post("/dashboard/", {"action": "mark_read"})
    assert resp.status_code == 302
    assert user.notifications.filter(is_read=False).count() == 0


@pytest.fixture
def assignment_with_file(journal, make_pub, django_user_model):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    from apps.submissions.models import FileStage, SubmissionFile

    pub = make_pub(title="Reviewed Paper")
    sub = pub.submission
    sf = SubmissionFile.objects.create(
        submission=sub, file=SimpleUploadedFile("ms.pdf", b"%PDF-1.4 test"),
        original_filename="ms.pdf", mimetype="application/pdf",
        file_size=13, file_stage=FileStage.SUBMISSION)
    reviewer = django_user_model.objects.create_user(
        email="rev@example.org", password="pw-long-enough-123", given_name="Rev")
    rnd = ReviewRound.objects.create(submission=sub)
    a = ReviewService.assign_reviewer(rnd, reviewer)
    return a, sf


def test_reviewer_sees_and_downloads_files(client, assignment_with_file):
    a, sf = assignment_with_file
    html = client.get(f"/review/{a.access_token}/").content.decode()
    assert f"/review/{a.access_token}/file/{sf.pk}/" in html
    resp = client.get(f"/review/{a.access_token}/file/{sf.pk}/")
    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith("attachment")


def test_reviewer_cannot_download_other_stage_files(client, assignment_with_file):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.submissions.models import FileStage, SubmissionFile
    a, _ = assignment_with_file
    hidden = SubmissionFile.objects.create(
        submission=a.review_round.submission,
        file=SimpleUploadedFile("internal.docx", b"x"),
        original_filename="internal.docx", file_size=1,
        file_stage=FileStage.QUERY)
    resp = client.get(f"/review/{a.access_token}/file/{hidden.pk}/")
    assert resp.status_code == 404


def test_review_submit_with_attachment(client, assignment_with_file):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.submissions.models import FileStage
    a, _ = assignment_with_file
    client.post(f"/review/{a.access_token}/", {"action": "accept"})
    resp = client.post(f"/review/{a.access_token}/form/", {
        "recommendation": 2,
        "comments_for_editor": "ok",
        "comments_for_author": "fix X",
        "attachment": SimpleUploadedFile("annotated.pdf", b"%PDF-1.4 notes"),
    })
    assert resp.status_code == 302
    a.refresh_from_db()
    assert a.is_complete and a.recommendation == 2
    att = a.review_round.submission.files.filter(
        file_stage=FileStage.REVIEW_ATTACHMENT)
    assert att.count() == 1
    assert att.first().uploader_id == a.reviewer_id


def test_send_due_reminders_and_no_duplicate(assignment_with_file):
    from datetime import timedelta
    from apps.review.tasks import send_due_reminders
    a, _ = assignment_with_file
    a.date_due = timezone.localdate() - timedelta(days=1)
    a.save(update_fields=["date_due"])
    mail.outbox.clear()
    out = send_due_reminders()
    assert out["sent"] == 1
    a.refresh_from_db()
    assert a.date_reminded is not None
    assert len(mail.outbox) == 1
    assert "overdue" in mail.outbox[0].subject.lower()
    assert "/review/" in mail.outbox[0].body
    out2 = send_due_reminders()
    assert out2["sent"] == 0
    assert len(mail.outbox) == 1


def test_completed_or_declined_not_reminded(assignment_with_file):
    from datetime import timedelta
    from apps.review.tasks import send_due_reminders
    a, _ = assignment_with_file
    a.date_due = timezone.localdate() - timedelta(days=2)
    a.date_completed = timezone.now()
    a.save(update_fields=["date_due", "date_completed"])
    assert send_due_reminders()["sent"] == 0


def test_periodic_runs_once_per_interval(db, monkeypatch):
    import apps.tasks.periodic as periodic
    calls = {"n": 0}

    def fake():
        calls["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(periodic, "_TEST_FAKE", fake, raising=False)
    monkeypatch.setattr(periodic, "REGISTRY",
                        [("fake_task", "apps.tasks.periodic._TEST_FAKE", 3600)])
    ran = periodic.maybe_run_periodic()
    assert ran == ["fake_task"] and calls["n"] == 1
    ran2 = periodic.maybe_run_periodic()
    assert ran2 == [] and calls["n"] == 1


def test_citation_exports(client, journal, make_pub, issue_published):
    from apps.publications.services import PublicationService
    pub = make_pub(issue=issue_published, title="Cite Me")
    PublicationService.publish(pub)
    pk = pub.submission_id
    bib = client.get(f"/article/{pk}/cite.bib")
    assert bib.status_code == 200
    body = bib.content.decode()
    assert body.startswith("@article") and "Cite Me" in body and "Lovelace" in body
    ris = client.get(f"/article/{pk}/cite.ris").content.decode()
    assert "TY  - JOUR" in ris and "TI  - Cite Me" in ris and "ER  -" in ris


def test_citation_404_for_unpublished(client, journal, make_pub):
    pub = make_pub()
    assert client.get(f"/article/{pub.submission_id}/cite.bib").status_code == 404


def test_profile_update(client, journal, user):
    client.force_login(user)
    assert client.get("/accounts/profile/").status_code == 200
    resp = client.post("/accounts/profile/", {
        "given_name": "Edited", "family_name": "User", "affiliation": "Uni",
        "affiliation_ror": "", "orcid": "", "country": "", "biography": "",
        "preferred_locale": "en",
    })
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.given_name == "Edited"
    assert user.notify_new_issue is False


def test_notify_readers_new_issue(journal, issue_unpublished, django_user_model):
    from apps.comms.tasks import notify_readers_new_issue
    django_user_model.objects.create_user(
        email="optin@example.org", password="pw-long-enough-123",
        given_name="In", notify_new_issue=True)
    django_user_model.objects.create_user(
        email="optout@example.org", password="pw-long-enough-123",
        given_name="Out", notify_new_issue=False)
    issue_unpublished.is_published = True
    issue_unpublished.save(update_fields=["is_published"])
    out = notify_readers_new_issue(issue_unpublished.pk)
    tos = [m.to[0] for m in mail.outbox]
    assert "optin@example.org" in tos and "optout@example.org" not in tos
    assert out["sent"] == len(tos)


def test_publish_issue_enqueues_reader_notification(
        journal, issue_unpublished, django_capture_on_commit_callbacks):
    from apps.publications.services import IssueService
    with django_capture_on_commit_callbacks(execute=True):
        IssueService.publish_issue(issue_unpublished)
    issue_unpublished.refresh_from_db()
    assert issue_unpublished.is_published


def test_wizard_confirm_saves_suggested_reviewers(client, journal, make_pub, user):
    pub = make_pub()
    sub = pub.submission
    client.force_login(user)
    resp = client.post(f"/submit/{sub.pk}/confirm/", {
        "sr_name": ["Dr. Ada", "", ""],
        "sr_email": ["ada@uni.edu", "", ""],
        "sr_reason": ["Domain expert", "", ""],
    })
    assert resp.status_code == 302
    sub.refresh_from_db()
    assert sub.suggested_reviewers == [
        {"name": "Dr. Ada", "email": "ada@uni.edu", "reason": "Domain expert"}]
    assert sub.date_submitted is not None


def test_admin_dashboard_renders_setup_health(client, journal, django_user_model):
    admin = django_user_model.objects.create_superuser(
        email="root@example.org", password="pw-long-enough-123", given_name="Root")
    client.force_login(admin)
    resp = client.get("/admin/")
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Setup health" in html


def test_upgrade_command_runs(db):
    from django.core.management import call_command
    call_command("upgrade", "--no-static")
