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

"""Plugin durumu (enable/disable) ve ayarları."""
from __future__ import annotations

from django.db import models


class PluginState(models.Model):
    plugin_key = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Plugin"
        verbose_name_plural = "Plugins"

    def __str__(self) -> str:
        return f"{self.plugin_key} ({'on' if self.enabled else 'off'})"

    def save(self, *args, **kwargs):
        prev = None
        if self.pk:
            prev = (PluginState.objects.filter(pk=self.pk)
                    .values_list("enabled", flat=True).first())
        super().save(*args, **kwargs)
        from .registry import registry
        registry.invalidate()
        if prev is not None and prev != self.enabled:
            plugin = registry.get(self.plugin_key)
            if plugin is not None:
                try:
                    plugin.on_enable() if self.enabled else plugin.on_disable()
                except Exception:
                    import logging
                    logging.getLogger("plugins").exception(
                        "plugin %s lifecycle failed", self.plugin_key)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        from .registry import registry
        registry.invalidate()


class PluginSetting(models.Model):
    plugin_key = models.CharField(max_length=64)
    journal = models.ForeignKey(
        "journals.Journal", null=True, blank=True, on_delete=models.CASCADE
    )
    key = models.CharField(max_length=64)
    value = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ("plugin_key", "journal", "key")
        verbose_name = "Plugin Setting"

    def __str__(self) -> str:
        return f"{self.plugin_key}.{self.key}"
