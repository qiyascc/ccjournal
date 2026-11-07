import io
import zipfile

import pytest
from django.core import mail

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(db, django_user_model):
    from django.contrib.auth.models import Group
    u = django_user_model.objects.create_user(
        email="p4-ed@example.org", password="pw-long-enough-123",
        given_name="Ed", is_staff=True)
    grp, _ = Group.objects.get_or_create(name="Editor")
    u.groups.add(grp)
    return u


def _docx_bytes(title="A Study Of Things", para="First paragraph of the study."):
    """mammoth'un okuyabileceği asgari .docx (zip) üretir."""
    doc = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:body>
  <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
    <w:r><w:t>{title}</w:t></w:r></w:p>
  <w:p><w:r><w:t>{para}</w:t></w:r></w:p>
 </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
 <Override PartName="/word/document.xml"
  ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
  Target="word/document.xml"/>
</Relationships>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


# --- Quick submit -------------------------------------------------------------

def test_quick_submit_docx_extracts_title_and_body(client, journal, section, user):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.submissions.models import Submission, SubmissionStatus
    client.force_login(user)
    assert b"Quick submit" in client.get("/submit/quick/").content
    resp = client.post("/submit/quick/", {
        "file": SimpleUploadedFile("manuscript.docx", _docx_bytes()),
        "agree": "on"})
    assert resp.status_code == 200 and b"Submitted!" in resp.content
    sub = Submission.objects.filter(submitter=user).latest("id")
    assert sub.status == SubmissionStatus.QUEUED
    t = sub.current_publication.tr(sub.locale)
    assert t.title == "A Study Of Things"
    assert "First paragraph" in t.body
    assert "A Study Of Things" not in t.body      # başlık gövdeden çıkarıldı
    assert sub.current_publication.authors.get().email == user.email


def test_quick_submit_non_docx_uses_filename(client, journal, section, user):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.submissions.models import Submission
    client.force_login(user)
    client.post("/submit/quick/", {
        "file": SimpleUploadedFile("my_great-paper.pdf", b"%PDF-1.4"),
        "agree": "on"})
    sub = Submission.objects.filter(submitter=user).latest("id")
    assert sub.current_publication.tr(sub.locale).title == "My great paper"


# --- İlerleme çubuğu ------------------------------------------------------------

def test_progress_timeline_and_median(client, journal, make_pub, editor,
                                      django_user_model):
    from datetime import timedelta

    from django.utils import timezone
    from apps.review.models import EditorialDecision, ReviewRound
    from apps.review.services import ReviewService, WorkflowService
    from apps.submissions.models import SubmissionStatus
    from apps.submissions.progress import timeline

    pub = make_pub(title="Progress Paper")
    sub = pub.submission
    sub.status = SubmissionStatus.QUEUED
    sub.date_submitted = timezone.now() - timedelta(days=10)
    sub.save(update_fields=["status", "date_submitted"])
    WorkflowService.record_decision(sub, editor,
                                    EditorialDecision.Decision.SEND_TO_REVIEW,
                                    notify_author=False)
    rnd = sub.review_rounds.first() or ReviewRound.objects.create(submission=sub)
    r1 = django_user_model.objects.create_user(
        email="pr-r1@example.org", password="pw-long-enough-123", given_name="R1")
    r2 = django_user_model.objects.create_user(
        email="pr-r2@example.org", password="pw-long-enough-123", given_name="R2")
    ReviewService.assign_reviewer(rnd, r1)
    a2 = ReviewService.assign_reviewer(rnd, r2)
    a2.date_completed = timezone.now()
    a2.save(update_fields=["date_completed"])

    data = timeline(sub)
    assert data["current_index"] == 1
    assert data["reviews_total"] == 2 and data["reviews_done"] == 1
    assert data["median_first_decision"] is not None
    html = client.get(f"/work/{sub.author_token}/").content.decode()
    assert "1 of 2 review reports received" in html
    assert "Median time to first decision" in html


# --- Entegrite ---------------------------------------------------------------------

def test_integrity_checks_flags(client, journal, make_pub, editor, monkeypatch):
    from apps.publications.models import Citation
    from apps.submissions import integrity

    pub = make_pub(title="Integrity Target")
    sub = pub.submission
    Citation.objects.create(publication=pub, seq=1, raw="Real work. doi ok",
                            doi="10.1/real")
    Citation.objects.create(publication=pub, seq=2, raw="Fake ref",
                            doi="10.1/fake")
    Citation.objects.create(publication=pub, seq=3, raw="Retracted one",
                            doi="10.1/retracted")
    for i in range(3):
        Citation.objects.create(publication=pub, seq=4 + i,
                                raw=f"Lovelace A. Self cite {i}.")
    sub.submitter.email = "author@mailinator.com"
    sub.submitter.save(update_fields=["email"])

    def fake_fetch(doi):
        if doi == "10.1/fake":
            return None
        if doi == "10.1/retracted":
            return {"update-to": [{"type": "retraction"}]}
        return {"title": ["ok"]}

    monkeypatch.setattr(integrity, "_crossref_fetch", fake_fetch)
    report = integrity.run_checks(sub, network=True)
    checks = report["checks"]
    assert report["overall"] == "alert"
    assert checks["references"]["unresolved"] == ["10.1/fake"]
    assert checks["references"]["retracted"] == ["10.1/retracted"]
    assert checks["emails"]["status"] == "warn"
    assert checks["self_citation"]["status"] == "warn"

    client.force_login(editor)
    html = client.get(f"/manage/integrity/{sub.pk}/").content.decode()
    assert "ALERT" in html and "10.1/retracted" in html and "mailinator.com" in html


def test_integrity_local_only_skips_network(journal, make_pub, monkeypatch):
    from apps.submissions import integrity
    pub = make_pub()
    monkeypatch.setattr(integrity, "_crossref_fetch",
                        lambda doi: (_ for _ in ()).throw(AssertionError("no net")))
    report = integrity.run_checks(pub.submission, network=False)
    assert report["network"] is False
    assert report["checks"]["references"]["status"] == "info"


# --- Kural motoru --------------------------------------------------------------------

def test_rule_all_reviews_done_notifies_editors(client, journal, make_pub, editor,
                                                django_user_model):
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub(title="Rules Paper")
    rnd = ReviewRound.objects.create(submission=pub.submission)
    rev = django_user_model.objects.create_user(
        email="rule-rev@example.org", password="pw-long-enough-123", given_name="R")
    a = ReviewService.assign_reviewer(rnd, rev)
    client.post(f"/review/{a.access_token}/", {"action": "accept"})
    mail.outbox.clear()
    client.post(f"/review/{a.access_token}/form/", {
        "recommendation": 1, "comments_for_editor": "", "comments_for_author": ""})
    assert editor.notifications.filter(type="reviews_complete").exists()
    assert any("decision needed" in m.subject.lower() for m in mail.outbox)


def test_rule_invite_reminder_and_stale_alert(journal, make_pub, editor,
                                              django_user_model):
    from datetime import timedelta

    from django.utils import timezone
    from apps.review.automation import run_rules
    from apps.review.models import ReviewAssignment, ReviewRound
    from apps.submissions.models import Stage, SubmissionStatus

    pub = make_pub(title="Stale Paper")
    sub = pub.submission
    sub.stage = Stage.REVIEW
    sub.status = SubmissionStatus.QUEUED
    sub.date_submitted = timezone.now() - timedelta(days=40)
    sub.save(update_fields=["stage", "status", "date_submitted"])
    rnd = ReviewRound.objects.create(submission=sub)
    rev = django_user_model.objects.create_user(
        email="silent-rev@example.org", password="pw-long-enough-123", given_name="S")
    a = ReviewAssignment.objects.create(review_round=rnd, reviewer=rev)
    ReviewAssignment.objects.filter(pk=a.pk).update(
        date_assigned=timezone.now() - timedelta(days=8))
    mail.outbox.clear()
    out = run_rules()
    assert out["invite_reminders"] == 1
    assert out["stale_alerts"] == 1
    a.refresh_from_db()
    assert a.date_reminded is not None
    assert editor.notifications.filter(type="stale_submission").exists()
    assert run_rules()["invite_reminders"] == 0      # tekrar spam yok


# --- Hakem tanınırlık ------------------------------------------------------------------

@pytest.fixture
def completed_assignment(journal, make_pub, django_user_model):
    from django.utils import timezone
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    pub = make_pub(title="Cert Paper")
    rev = django_user_model.objects.create_user(
        email="cert-rev@example.org", password="pw-long-enough-123",
        given_name="Certy", family_name="Reviewer")
    rnd = ReviewRound.objects.create(submission=pub.submission)
    a = ReviewService.assign_reviewer(rnd, rev)
    a.date_completed = timezone.now()
    a.save(update_fields=["date_completed"])
    return a


def test_certificate_pdf_and_gating(client, completed_assignment):
    a = completed_assignment
    resp = client.get(f"/review/{a.access_token}/certificate.pdf")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
    from apps.review.models import ReviewAssignment
    b = ReviewAssignment.objects.create(review_round=a.review_round,
                                        reviewer=a.reviewer.__class__.objects.create_user(
                                            email="x2@example.org",
                                            password="pw-long-enough-123",
                                            given_name="X"))
    assert client.get(f"/review/{b.access_token}/certificate.pdf").status_code == 404


def test_year_summary_and_public_page(client, journal, completed_assignment):
    from django.utils import timezone
    from apps.review.certificates import send_year_summary, year_stats
    from apps.review.services import ReviewerService
    a = completed_assignment
    year = timezone.now().year
    stats = year_stats(a.reviewer, year)
    assert stats["completed"] == 1
    mail.outbox.clear()
    assert send_year_summary(a.reviewer, year) is True
    assert "Thank you for reviewing" in mail.outbox[0].subject
    prof = ReviewerService.ensure_profile(a.reviewer)
    prof.public_listing = True
    prof.save(update_fields=["public_listing"])
    html = client.get("/reviewers/").content.decode()
    assert "Certy Reviewer" in html and "1 review" in html


# --- Tek dokunuş kabul --------------------------------------------------------------------

def test_quick_reply_accept_and_decline(journal, make_pub, django_user_model):
    from apps.review.models import ReviewRound
    from apps.review.quick_response import handle_reply
    from apps.review.services import ReviewService
    pub = make_pub(title="Msg Paper")
    rev = django_user_model.objects.create_user(
        email="msg-rev@example.org", password="pw-long-enough-123", given_name="M")
    rnd = ReviewRound.objects.create(submission=pub.submission)
    a = ReviewService.assign_reviewer(rnd, rev)
    assert handle_reply(rev, "merhaba") is None       # ilgisiz metin
    out = handle_reply(rev, "1")
    assert "Accepted" in out and a.access_token in out
    a.refresh_from_db()
    assert a.date_confirmed is not None
    b = ReviewService.assign_reviewer(ReviewRound.objects.create(
        submission=make_pub(title="Msg2").submission), rev)
    out2 = handle_reply(rev, "2")
    assert "Declined" in out2
    b.refresh_from_db()
    assert b.declined is True
    assert "no review invitations" in handle_reply(rev, "1")


def test_channel_reply_webhook(client, journal, make_pub, django_user_model):
    import json
    from apps.comms.hook_views import hook_secret
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService
    rev = django_user_model.objects.create_user(
        email="wa-rev@example.org", password="pw-long-enough-123",
        given_name="W", whatsapp_number="994501234567")
    rnd = ReviewRound.objects.create(submission=make_pub(title="WA Paper").submission)
    a = ReviewService.assign_reviewer(rnd, rev)
    secret = hook_secret()
    resp = client.post("/hooks/channel-reply/",
                       data=json.dumps({"channel": "whatsapp",
                                        "address": "994501234567", "text": "1"}),
                       content_type="application/json",
                       HTTP_X_CCJ_HOOK_SECRET=secret)
    assert resp.status_code == 200
    assert a.access_token in resp.json()["reply"]
    a.refresh_from_db()
    assert a.date_confirmed is not None
    assert client.post("/hooks/channel-reply/", data="{}",
                       content_type="application/json",
                       HTTP_X_CCJ_HOOK_SECRET="wrong").status_code == 403
