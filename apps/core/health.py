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

"""Health endpoint — DB + cache + storage; JSON döner (şablon bağımlılığı yok)."""
import asyncio

from health_check.views import HealthCheckView


class JsonHealthCheckView(HealthCheckView):
    checks = [
        "health_check.checks.Database",
        "health_check.checks.Cache",
        "health_check.checks.Storage",
    ]

    async def get(self, request, *args, **kwargs):
        with self.get_executor() as executor:
            self.results = await asyncio.gather(
                *(check.get_result(executor) for check in self.get_checks()))
        status_code = 503 if any(r.error for r in self.results) else 200
        return self.render_to_response_json(status_code)
