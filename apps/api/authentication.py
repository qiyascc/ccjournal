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

"""API key kimlik doğrulama — Authorization: Api-Key <key> / Bearer <key> / X-Api-Key."""
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ApiKeyAuthentication(BaseAuthentication):
    keyword_set = {"api-key", "bearer", "apikey", "token"}

    def authenticate(self, request):
        raw = None
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if auth:
            parts = auth.split()
            if len(parts) == 2 and parts[0].lower() in self.keyword_set:
                raw = parts[1]
        if not raw:
            raw = request.META.get("HTTP_X_API_KEY")
        if not raw:
            return None
        from apps.accounts.models import ApiKey
        key = ApiKey.resolve(raw)
        if key is None:
            raise AuthenticationFailed("Invalid or inactive API key.")
        if not key.user.is_active:
            raise AuthenticationFailed("User account is inactive.")
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return (key.user, key)

    def authenticate_header(self, request):
        return "Api-Key"


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class ApiKeyScheme(OpenApiAuthenticationExtension):
        target_class = "apps.api.authentication.ApiKeyAuthentication"
        name = "ApiKeyAuth"

        def get_security_definition(self, auto_schema):
            return {"type": "apiKey", "in": "header", "name": "Authorization",
                    "description": "Personal API key as: `Api-Key <key>`"}
except Exception:
    pass
