from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.app.core.config import Settings
from backend.app.services.repository import StateRepository
from backend.app.services.sync_service import run_sync_job

DAY_TO_INDEX = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


class WeeklyScanScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if not self.settings.weekly_scan_enabled or self._task:
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        while True:
            next_run = next_weekly_run(
                self.settings.weekly_scan_day,
                self.settings.weekly_scan_time,
                self.settings.weekly_scan_timezone,
            )
            now = datetime.now(ZoneInfo(self.settings.weekly_scan_timezone))
            await asyncio.sleep(max(0.0, (next_run - now).total_seconds()))
            for job_id in create_weekly_scan_jobs(self.settings):
                asyncio.create_task(run_sync_job(job_id))


def create_weekly_scan_jobs(settings: Settings) -> list[str]:
    repository = StateRepository(settings.sqlite_path)
    job_ids: list[str] = []
    for account in settings.enabled_feishu_accounts:
        if not account.configured:
            continue
        if repository.has_running_weekly_job(account.account_id):
            continue
        job = repository.create_job(
            scope_type="account",
            scope_id=account.account_id,
            account_id=account.account_id,
        )
        job_ids.append(job["job_id"])
    return job_ids


def next_weekly_run(day: str, hhmm: str, timezone_name: str) -> datetime:
    timezone = ZoneInfo(timezone_name)
    now = datetime.now(timezone)
    target_day = DAY_TO_INDEX[day.strip().upper()]
    target_time = _parse_hhmm(hhmm)
    candidate = datetime.combine(now.date(), target_time, tzinfo=timezone)
    days_ahead = (target_day - now.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


def _parse_hhmm(value: str) -> time:
    hour_raw, minute_raw = value.split(":", 1)
    return time(hour=int(hour_raw), minute=int(minute_raw))
