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

"""Serializer'lar — CountryField eşlemeli taban + fabrika + hassas modeller."""
from django_countries.fields import CountryField as ModelCountryField
from django_countries.serializer_fields import CountryField as CountrySerializerField
from rest_framework import serializers

from apps.accounts.models import ApiKey, User


class BaseModelSerializer(serializers.ModelSerializer):
    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        ModelCountryField: CountrySerializerField,
    }


def make_serializer(model, exclude=None):
    meta_attrs = {"model": model}
    if exclude:
        meta_attrs["exclude"] = tuple(exclude)
    else:
        meta_attrs["fields"] = "__all__"
    Meta = type("Meta", (), meta_attrs)
    return type(f"{model.__name__}Serializer", (BaseModelSerializer,), {"Meta": Meta})


class UserSerializer(BaseModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "given_name", "family_name", "affiliation",
                  "country", "orcid", "is_active", "is_staff", "roles", "created_at")
        read_only_fields = ("is_staff", "roles", "created_at")

    def get_roles(self, obj):
        return list(obj.groups.values_list("name", flat=True))


class UserWriteSerializer(BaseModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("id", "email", "given_name", "family_name", "affiliation",
                  "country", "orcid", "is_active", "password")

    def create(self, validated):
        pw = validated.pop("password", None)
        user = User(**validated)
        if pw:
            user.set_password(pw)
        user.save()
        return user

    def update(self, instance, validated):
        pw = validated.pop("password", None)
        for k, val in validated.items():
            setattr(instance, k, val)
        if pw:
            instance.set_password(pw)
        instance.save()
        return instance


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ("id", "name", "prefix", "is_active", "created_at", "last_used_at")
        read_only_fields = ("prefix", "created_at", "last_used_at")
