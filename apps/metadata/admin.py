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

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Tombstone


@admin.register(Tombstone)
class TombstoneAdmin(ModelAdmin):
    list_display = ("oai_identifier", "title_snapshot", "doi_snapshot", "date_deleted")
    search_fields = ("oai_identifier", "title_snapshot", "doi_snapshot")
    list_filter = ("journal",)
    readonly_fields = ("date_deleted",)


from apps.core.models.identifiers import Doi


@admin.register(Doi)
class DoiAdmin(ModelAdmin):
    list_display = ("doi", "journal", "status", "agency", "registered_at")
    list_filter = ("status", "agency", "journal")
    search_fields = ("doi",)
    readonly_fields = ("doi", "journal", "registered_at", "last_response")
    actions = ["action_deposit"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Deposit selected DOIs to Crossref")
    def action_deposit(self, request, queryset):
        from django.contrib import messages
        from apps.metadata.crossref import deposit_publications
        from apps.publications.models import Publication
        pub_ids = set(Publication.objects.filter(doi__in=queryset)
                      .values_list("id", flat=True))
        pub_ids |= set(Publication.objects.filter(galleys__doi__in=queryset)
                       .values_list("id", flat=True))
        pubs = list(Publication.objects.filter(id__in=pub_ids))
        if not pubs:
            self.message_user(request, "No publications linked to these DOIs.",
                              level=messages.WARNING)
            return
        result = deposit_publications(pubs)
        if result.get("dry_run"):
            self.message_user(request, "Crossref credentials not set — XML generated "
                              "but not sent (config.ini [crossref]).",
                              level=messages.WARNING)
        elif result.get("ok"):
            self.message_user(request, f"Submitted {result['submitted']} DOI(s) to Crossref.")
        else:
            self.message_user(request, f"Deposit failed: {result.get('detail')}",
                              level=messages.ERROR)
