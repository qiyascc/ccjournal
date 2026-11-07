import pytest

pytestmark = pytest.mark.django_db

HOST = "journal.ubermensch.cc"


def _sub(journal, user, stage, status):
    from apps.submissions.models import Submission
    return Submission.objects.create(journal=journal, submitter=user, stage=stage, status=status)


def test_columns_group_by_stage_and_exclude_terminal(journal, user):
    from apps.review.board import _columns
    from apps.submissions.models import Stage, SubmissionStatus

    _sub(journal, user, Stage.SUBMISSION, SubmissionStatus.QUEUED)
    _sub(journal, user, Stage.REVIEW, SubmissionStatus.QUEUED)
    _sub(journal, user, Stage.REVIEW, SubmissionStatus.QUEUED)
    _sub(journal, user, Stage.PRODUCTION, SubmissionStatus.PUBLISHED)
    _sub(journal, user, Stage.EDITING, SubmissionStatus.DECLINED)

    counts = {c["stage"]: c["count"] for c in _columns()}
    assert counts[Stage.SUBMISSION] == 1
    assert counts[Stage.REVIEW] == 2
    assert counts[Stage.EDITING] == 0
    assert counts[Stage.PRODUCTION] == 0


def test_board_redirects_anonymous(client):
    r = client.get("/manage/board/", HTTP_HOST=HOST)
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_board_columns_forbidden_for_anon(client):
    assert client.get("/manage/board/columns/", HTTP_HOST=HOST).status_code == 403


def test_board_renders_for_superuser(client, django_user_model):
    su = django_user_model.objects.create_superuser(
        email="su@example.org", password="pw-long-enough-123", given_name="Su")
    client.force_login(su)
    r = client.get("/manage/board/", HTTP_HOST=HOST)
    assert r.status_code == 200
    assert b"Editorial board" in r.content


def test_ping_creates_presence(client, django_user_model):
    from apps.review.models import BoardPresence
    su = django_user_model.objects.create_superuser(
        email="su2@example.org", password="pw-long-enough-123", given_name="Su")
    client.force_login(su)
    assert client.post("/manage/board/ping/", HTTP_HOST=HOST).status_code == 204
    assert BoardPresence.objects.filter(user=su).exists()
