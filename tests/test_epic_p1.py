import pytest
from django.core import mail
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(db, django_user_model):
    from django.contrib.auth.models import Group
    u = django_user_model.objects.create_user(
        email="chief@example.org", password="pw-long-enough-123",
        given_name="Chief", is_staff=True)
    grp, _ = Group.objects.get_or_create(name="Editor")
    u.groups.add(grp)
    return u


@pytest.fixture
def assignment(journal, make_pub, django_user_model):
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub(title="Formed Paper")
    reviewer = django_user_model.objects.create_user(
        email="rf-rev@example.org", password="pw-long-enough-123", given_name="Rev")
    rnd = ReviewRound.objects.create(submission=pub.submission)
    return ReviewService.assign_reviewer(rnd, reviewer)


def _make_form(journal):
    from apps.review.models import ReviewFormItem, ReviewFormTemplate
    tpl = ReviewFormTemplate.objects.create(journal=journal, title="Quality form",
                                            is_active=True)
    q1 = ReviewFormItem.objects.create(template=tpl, seq=1, label="Overall quality?",
                                       kind="radio", choices=["Low", "High"],
                                       required=True)
    q2 = ReviewFormItem.objects.create(template=tpl, seq=2, label="Free comments",
                                       kind="textarea", required=False)
    return tpl, q1, q2


def test_review_form_rendered_and_saved(client, journal, assignment):
    tpl, q1, q2 = _make_form(journal)
    a = assignment
    client.post(f"/review/{a.access_token}/", {"action": "accept"})
    html = client.get(f"/review/{a.access_token}/form/").content.decode()
    assert "Overall quality?" in html and "Quality form" in html
    resp = client.post(f"/review/{a.access_token}/form/", {
        "recommendation": 1, "comments_for_editor": "", "comments_for_author": ""})
    a.refresh_from_db()
    assert resp.status_code == 200 and not a.is_complete
    resp = client.post(f"/review/{a.access_token}/form/", {
        "recommendation": 1, "comments_for_editor": "", "comments_for_author": "",
        f"rf_{q1.pk}": "High", f"rf_{q2.pk}": "Nice methods."})
    assert resp.status_code == 302
    a.refresh_from_db()
    assert a.is_complete
    assert {"item": q1.pk, "label": "Overall quality?", "value": "High"} in a.form_responses
    assert any(r["value"] == "Nice methods." for r in a.form_responses)


def test_single_active_review_form_per_journal(journal, editor, client):
    from apps.review.models import ReviewFormTemplate
    _make_form(journal)
    client.force_login(editor)
    resp = client.post("/admin/review/reviewformtemplate/add/", {
        "journal": journal.pk, "title": "Second form", "description": "",
        "is_active": "on",
        "items-TOTAL_FORMS": 0, "items-INITIAL_FORMS": 0,
    })
    assert resp.status_code == 302
    active = ReviewFormTemplate.objects.filter(journal=journal, is_active=True)
    assert active.count() == 1 and active.first().title == "Second form"


def test_decide_with_email_two_step(client, journal, make_pub, editor):
    from apps.review.models import EditorialDecision
    from apps.submissions.models import SubmissionStatus
    pub = make_pub(title="Decision Paper")
    sub = pub.submission
    client.force_login(editor)
    url = "/admin/submissions/submission/"
    sel = {"action": "action_decide_with_email", "_selected_action": [sub.pk]}
    resp = client.post(url, sel)
    assert resp.status_code == 200 and b"Step 1" in resp.content
    resp = client.post(url, {**sel, "preview": "1",
                             "decision": EditorialDecision.Decision.DECLINE,
                             "note": "Out of scope."})
    html = resp.content.decode()
    assert "Step 2" in html and "Out of scope." in html
    mail.outbox.clear()
    resp = client.post(url, {**sel, "apply": "1",
                             "decision": EditorialDecision.Decision.DECLINE,
                             "note": "Out of scope.",
                             "subject": "Custom decision subject",
                             "body": "Dear author, edited body.",
                             "send_email": "on"})
    assert resp.status_code == 302
    sub.refresh_from_db()
    assert sub.status == SubmissionStatus.DECLINED
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Custom decision subject"


def test_record_decision_notify_author_false_suppresses_email(journal, make_pub, editor):
    from apps.review.models import EditorialDecision
    from apps.review.services import WorkflowService
    pub = make_pub()
    mail.outbox.clear()
    WorkflowService.record_decision(pub.submission, editor,
                                    EditorialDecision.Decision.ACCEPT,
                                    notify_author=False)
    assert len(mail.outbox) == 0
    assert pub.submission.submitter.notifications.count() >= 1


def test_files_manager_upload_promote_download(client, journal, make_pub, editor):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.submissions.models import FileStage
    pub = make_pub()
    sub = pub.submission
    client.force_login(editor)
    page = client.get(f"/manage/files/{sub.pk}/")
    assert page.status_code == 200
    resp = client.post(f"/manage/files/{sub.pk}/", {
        "action": "upload", "stage": FileStage.COPYEDIT,
        "file": SimpleUploadedFile("edit.docx", b"draft")})
    assert resp.status_code == 302
    sf = sub.files.get(file_stage=FileStage.COPYEDIT)
    resp = client.post(f"/manage/files/{sub.pk}/",
                       {"action": "promote", "file_id": sf.pk})
    assert resp.status_code == 302
    promoted = sub.files.get(file_stage=FileStage.PROOF)
    assert promoted.source_file_id == sf.pk
    assert promoted.file.name != sf.file.name
    dl = client.get(f"/manage/files/{sub.pk}/dl/{promoted.pk}/")
    assert dl.status_code == 200
    client.logout()
    assert client.get(f"/manage/files/{sub.pk}/").status_code == 302


def test_usage_report_and_csvs(client, journal, make_pub, editor):
    from apps.stats.models import Metric, MetricDay
    pub = make_pub()
    MetricDay.objects.create(submission=pub.submission, metric=Metric.ABSTRACT_VIEW,
                             date=timezone.localdate(), count=7)
    client.force_login(editor)
    html = client.get("/reports/usage/").content.decode()
    assert "Most-read articles" in html and ">7<" in html
    csv_resp = client.get("/reports/usage.csv")
    assert csv_resp.status_code == 200 and b"Abstract views" in csv_resp.content
    ed = client.get("/reports/editorial.csv")
    assert ed.status_code == 200 and b"Acceptance rate" in ed.content


def test_invitation_new_user_accept(client, journal):
    from apps.accounts.models import Role, UserInvitation
    inv = UserInvitation.objects.create(email="newbie@example.org",
                                        journal=journal, role=Role.REVIEWER)
    assert inv.send() is True
    assert any("/accounts/invite/" in m.body for m in mail.outbox)
    page = client.get(f"/accounts/invite/{inv.token}/")
    assert page.status_code == 200 and b"Create account" in page.content
    resp = client.post(f"/accounts/invite/{inv.token}/", {
        "given_name": "New", "family_name": "Bie",
        "password": "a-strong-pass-99"})
    assert resp.status_code == 302
    inv.refresh_from_db()
    assert inv.accepted_at is not None
    user = inv.accepted_by
    assert user.email == "newbie@example.org"
    assert user.memberships.filter(journal=journal, role=Role.REVIEWER).exists()
    assert "Reviewer" in user.role_names
    assert client.get(f"/accounts/invite/{inv.token}/").status_code == 410


def test_invitation_existing_user_needs_login(client, journal, user):
    from apps.accounts.models import Role, UserInvitation
    inv = UserInvitation.objects.create(email=user.email, journal=journal,
                                        role=Role.SECTION_EDITOR)
    page = client.get(f"/accounts/invite/{inv.token}/")
    assert b"Sign in" in page.content
    client.force_login(user)
    resp = client.post(f"/accounts/invite/{inv.token}/")
    assert resp.status_code == 302
    assert user.memberships.filter(role=Role.SECTION_EDITOR).exists()


def test_merge_users_moves_records(journal, make_pub, django_user_model):
    from apps.accounts.merge import merge_users
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub()
    src = pub.submission.submitter
    target = django_user_model.objects.create_user(
        email="canonical@example.org", password="pw-long-enough-123", given_name="Canon")
    rnd = ReviewRound.objects.create(submission=pub.submission)
    ReviewService.assign_reviewer(rnd, src)
    moved = merge_users(src, target)
    src.refresh_from_db()
    pub.submission.refresh_from_db()
    assert moved >= 2
    assert pub.submission.submitter_id == target.pk
    assert rnd.assignments.first().reviewer_id == target.pk
    assert src.is_active is False


def test_login_lockout_after_failures(client, journal, user):
    for _ in range(5):
        client.post("/accounts/login/", {"username": user.email, "password": "wrong!"})
    resp = client.post("/accounts/login/",
                       {"username": user.email, "password": "pw-long-enough-123"})
    assert resp.status_code == 429
    assert b"Too many failed attempts" in resp.content


def test_login_ok_before_limit(client, journal, user):
    for _ in range(3):
        client.post("/accounts/login/", {"username": user.email, "password": "wrong!"})
    resp = client.post("/accounts/login/",
                       {"username": user.email, "password": "pw-long-enough-123"})
    assert resp.status_code == 302
