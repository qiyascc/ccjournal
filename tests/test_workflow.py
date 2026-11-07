import pytest

pytestmark = pytest.mark.django_db


def _decide(pub, user, decision, **kw):
    from apps.review.services import WorkflowService
    return WorkflowService.record_decision(pub.submission, user, decision, **kw)


def test_send_to_review_sets_stage_and_opens_round(make_pub, user):
    from apps.review.models import EditorialDecision
    from apps.submissions.models import Stage

    pub = make_pub()
    _decide(pub, user, EditorialDecision.Decision.SEND_TO_REVIEW)
    sub = pub.submission
    sub.refresh_from_db()
    assert sub.stage == Stage.REVIEW
    assert sub.review_rounds.filter(stage=Stage.REVIEW).exists()


def test_accept_moves_to_editing(make_pub, user):
    from apps.review.models import EditorialDecision
    from apps.submissions.models import Stage

    pub = make_pub()
    _decide(pub, user, EditorialDecision.Decision.ACCEPT)
    sub = pub.submission
    sub.refresh_from_db()
    assert sub.stage == Stage.EDITING


def test_send_to_production_sets_stage(make_pub, user):
    from apps.review.models import EditorialDecision
    from apps.submissions.models import Stage

    pub = make_pub()
    _decide(pub, user, EditorialDecision.Decision.SEND_TO_PRODUCTION)
    sub = pub.submission
    sub.refresh_from_db()
    assert sub.stage == Stage.PRODUCTION


def test_decline_sets_declined_status(make_pub, user):
    from apps.review.models import EditorialDecision
    from apps.submissions.models import SubmissionStatus

    pub = make_pub()
    _decide(pub, user, EditorialDecision.Decision.DECLINE)
    sub = pub.submission
    sub.refresh_from_db()
    assert sub.status == SubmissionStatus.DECLINED


def test_decision_is_recorded(make_pub, user):
    from apps.review.models import EditorialDecision

    pub = make_pub()
    ed = _decide(pub, user, EditorialDecision.Decision.SEND_TO_REVIEW)
    assert ed.pk is not None
    assert EditorialDecision.objects.filter(submission=pub.submission).count() == 1


def test_ensure_review_round_is_idempotent_while_open(make_pub):
    from apps.review.services import WorkflowService

    pub = make_pub()
    r1 = WorkflowService.ensure_review_round(pub.submission)
    r2 = WorkflowService.ensure_review_round(pub.submission)
    assert r1.id == r2.id


def test_assign_reviewer_moves_round_in_review(make_pub, django_user_model):
    from apps.review.models import ReviewRound
    from apps.review.services import ReviewService, WorkflowService

    pub = make_pub()
    rnd = WorkflowService.ensure_review_round(pub.submission)
    reviewer = django_user_model.objects.create_user(
        email="rev@example.org", password="pw-long-enough-123", given_name="Rev")
    ReviewService.assign_reviewer(rnd, reviewer)
    rnd.refresh_from_db()
    assert rnd.status == ReviewRound.Status.IN_REVIEW
    assert rnd.assignments.filter(reviewer=reviewer).exists()
