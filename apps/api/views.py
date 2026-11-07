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

"""ViewSet'ler — fabrika + özel (sahiplik, publish, /me, API key)."""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.accounts.models import ApiKey, User
from .permissions import (
    IsOwnerOfApiKey, PublicReadRoleWrite, RoleModelPermissions, SubmissionPermission,
)
from .serializers import (
    ApiKeySerializer, UserSerializer, UserWriteSerializer, make_serializer,
)

_BACKENDS = [DjangoFilterBackend, SearchFilter, OrderingFilter]


def make_viewset(model, *, permission, serializer=None, search=(), queryset=None):
    attrs = {
        "queryset": queryset if queryset is not None else model._default_manager.all(),
        "serializer_class": serializer or make_serializer(model),
        "permission_classes": [permission],
        "filter_backends": _BACKENDS,
        "search_fields": list(search),
        "ordering": ["-id"],
    }
    return type(f"{model.__name__}ViewSet", (viewsets.ModelViewSet,), attrs)


class _PublicQSMixin:
    published_filter = {}

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if self.published_filter and not (u and u.is_staff):
            return qs.filter(**self.published_filter)
        return qs


def public_viewset(model, *, published_filter=None, search=(), serializer=None):
    base = make_viewset(model, permission=PublicReadRoleWrite, serializer=serializer, search=search)
    return type(model.__name__ + "PublicViewSet", (_PublicQSMixin, base),
                {"published_filter": published_filter or {}})


def submission_viewset():
    from apps.submissions.models import Submission
    ser = make_serializer(Submission)

    class SubmissionViewSet(viewsets.ModelViewSet):
        serializer_class = ser
        permission_classes = [SubmissionPermission]
        filter_backends = _BACKENDS
        search_fields = ["id"]
        ordering = ["-id"]

        def get_queryset(self):
            if getattr(self, "swagger_fake_view", False):
                return Submission._default_manager.none()
            qs = Submission._default_manager.all()
            u = self.request.user
            return qs if u.is_staff else qs.filter(submitter=u)

        def perform_create(self, serializer):
            serializer.save(submitter=self.request.user)

        @action(detail=True, methods=["post"])
        def decision(self, request, pk=None):
            """Editöryal karar kaydet. body: {decision:int, comment?:str}"""
            sub = self.get_object()
            if not request.user.is_staff:
                return Response({"detail": "Forbidden."}, status=403)
            from apps.review.services import WorkflowService
            try:
                d = int(request.data.get("decision"))
            except (TypeError, ValueError):
                return Response({"detail": "decision (int) required."}, status=400)
            try:
                WorkflowService.record_decision(sub, request.user, d,
                                                comment=request.data.get("comment", ""))
            except DjangoValidationError as e:
                raise DRFValidationError(getattr(e, "messages", [str(e)]))
            return Response({"status": "recorded", "decision": d})

    return SubmissionViewSet


def publication_viewset():
    from apps.publications.models import Publication, PublicationStatus
    from apps.publications.services import PublicationService
    ser = make_serializer(Publication)

    class PublicationViewSet(_PublicQSMixin, viewsets.ModelViewSet):
        queryset = Publication._default_manager.all()
        serializer_class = ser
        permission_classes = [PublicReadRoleWrite]
        filter_backends = _BACKENDS
        ordering = ["-id"]
        published_filter = {"status": PublicationStatus.PUBLISHED}

        @action(detail=True, methods=["post"], permission_classes=[RoleModelPermissions])
        def publish(self, request, pk=None):
            try:
                pub = PublicationService.publish(self.get_object(),
                                                 force=bool(request.data.get("force")))
            except DjangoValidationError as e:
                raise DRFValidationError(getattr(e, "messages", [str(e)]))
            return Response({"status": "published", "id": pub.id})

        @action(detail=True, methods=["post"], permission_classes=[RoleModelPermissions])
        def unpublish(self, request, pk=None):
            PublicationService.unpublish(self.get_object())
            return Response({"status": "unpublished"})

    return PublicationViewSet


def issue_viewset():
    from apps.journals.models import Issue
    from apps.publications.services import IssueService

    class IssueViewSet(_PublicQSMixin, viewsets.ModelViewSet):
        queryset = Issue._default_manager.all()
        serializer_class = make_serializer(Issue)
        permission_classes = [PublicReadRoleWrite]
        filter_backends = _BACKENDS
        ordering = ["-id"]
        published_filter = {"is_published": True}

        @action(detail=True, methods=["post"], permission_classes=[RoleModelPermissions])
        def publish(self, request, pk=None):
            try:
                IssueService.publish_issue(self.get_object())
            except DjangoValidationError as e:
                raise DRFValidationError(getattr(e, "messages", [str(e)]))
            return Response({"status": "published"})

    return IssueViewSet


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("-id")
    permission_classes = [RoleModelPermissions]
    filter_backends = _BACKENDS
    search_fields = ["email", "given_name", "family_name", "affiliation"]

    def get_serializer_class(self):
        return UserWriteSerializer if self.action in ("create", "update", "partial_update") else UserSerializer

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user).data)


class ApiKeyViewSet(viewsets.ModelViewSet):
    serializer_class = ApiKeySerializer
    permission_classes = [IsOwnerOfApiKey]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ApiKey.objects.none()
        return ApiKey.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        name = request.data.get("name", "")
        obj, raw = ApiKey.generate(request.user, name=name)
        data = ApiKeySerializer(obj).data
        data["key"] = raw
        data["detail"] = "Store this key now; it will not be shown again."
        return Response(data, status=status.HTTP_201_CREATED)
