"""Scheduler engine for YOUTUBE AI AGENT.

TODO: Keep job registration, retry logic, and job state control centralized here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class JobDefinition:
    """Describe one scheduler job in a configuration-friendly format."""

    name: str
    func: Callable[..., Any]
    trigger: Any
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None
    replace_existing: bool = True


class JobManager:
    """Manage recurring jobs, retries, and pause/resume operations."""

    def __init__(self) -> None:
        """Initialize the APScheduler-backed job manager."""

        self._scheduler = BackgroundScheduler(
            timezone=settings.scheduler_timezone,
            executors={"default": ThreadPoolExecutor(max_workers=4)},
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
        )
        self._configured = False

    def configure(self) -> None:
        """Register the default recurring jobs if they have not been configured yet."""

        if self._configured:
            return

        self.register_job(self._every_30_minutes_job())
        self.register_job(self._daily_report_job())
        self.register_job(self._weekly_report_job())
        self.register_job(self._monthly_report_job())
        self._scheduler.add_listener(self._handle_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)
        self._configured = True

    def start(self) -> None:
        """Start the scheduler after registering configured jobs."""

        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled by configuration")
            return
        self.configure()
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started with {} jobs", len(self.list_jobs()))

    def shutdown(self) -> None:
        """Shut down the scheduler if it is currently running."""

        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def register_job(self, definition: JobDefinition) -> Job:
        """Register a scheduler job and wrap it with retry handling."""

        wrapped = self._with_retry(definition.name, definition.func)
        job = self._scheduler.add_job(
            wrapped,
            trigger=definition.trigger,
            id=definition.name,
            name=definition.name,
            args=definition.args,
            kwargs=definition.kwargs or {},
            replace_existing=definition.replace_existing,
        )
        logger.info("Registered job {}", definition.name)
        return job

    def pause_job(self, job_id: str) -> None:
        """Pause a specific scheduled job."""

        self._scheduler.pause_job(job_id)
        logger.info("Paused job {}", job_id)

    def resume_job(self, job_id: str) -> None:
        """Resume a specific scheduled job."""

        self._scheduler.resume_job(job_id)
        logger.info("Resumed job {}", job_id)

    def pause_all(self) -> None:
        """Pause all scheduled jobs."""

        self._scheduler.pause()
        logger.info("Paused all scheduled jobs")

    def resume_all(self) -> None:
        """Resume all scheduled jobs."""

        self._scheduler.resume()
        logger.info("Resumed all scheduled jobs")

    def list_jobs(self) -> list[dict[str, str | None]]:
        """Return a snapshot of the registered jobs."""

        jobs: list[dict[str, str | None]] = []
        for job in self._scheduler.get_jobs():
            jobs.append({"id": job.id, "name": job.name, "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None})
        return jobs

    def _with_retry(self, job_name: str, func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a job function with configured retry behavior and logging."""

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Execute the job with retry handling."""

            last_error: Exception | None = None
            for attempt in range(1, settings.scheduler_retry_attempts + 1):
                try:
                    logger.info("Running job {} attempt {}", job_name, attempt)
                    return func(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - runtime safety
                    last_error = exc
                    logger.exception("Job {} failed on attempt {}", job_name, attempt)
                    if attempt < settings.scheduler_retry_attempts:
                        time.sleep(settings.scheduler_retry_delay_seconds)
            if last_error is not None:
                raise last_error

        return wrapped

    def _every_30_minutes_job(self) -> JobDefinition:
        """Build the configured 30-minute recurring job."""

        return JobDefinition(
            name="every_30_minutes",
            func=self._no_op_job,
            trigger=IntervalTrigger(minutes=settings.scheduler_every_30_minutes, timezone=settings.scheduler_timezone),
        )

    def _daily_report_job(self) -> JobDefinition:
        """Build the daily report job that runs every morning."""

        return JobDefinition(
            name="daily_report",
            func=self._daily_report_task,
            trigger=CronTrigger(
                hour=settings.daily_report_hour,
                minute=settings.daily_report_minute,
                timezone=settings.scheduler_timezone,
            ),
        )

    def _weekly_report_job(self) -> JobDefinition:
        """Build the weekly report job that runs every Sunday morning."""

        return JobDefinition(
            name="weekly_report",
            func=self._weekly_report_task,
            trigger=CronTrigger(
                day_of_week=settings.weekly_report_day_of_week,
                hour=settings.weekly_report_hour,
                minute=settings.weekly_report_minute,
                timezone=settings.scheduler_timezone,
            ),
        )

    def _monthly_report_job(self) -> JobDefinition:
        """Build the monthly report job that runs on a configurable day."""

        return JobDefinition(
            name="monthly_report",
            func=self._monthly_report_task,
            trigger=CronTrigger(
                day=settings.monthly_report_day,
                hour=settings.monthly_report_hour,
                minute=settings.monthly_report_minute,
                timezone=settings.scheduler_timezone,
            ),
        )

    def _no_op_job(self) -> None:
        """Placeholder recurring job for the 30-minute scheduler slot."""

        logger.info("30-minute job tick at {}", datetime.utcnow().isoformat())

    def _daily_report_task(self) -> None:
        """Placeholder daily report task until collectors are implemented."""

        logger.info("Daily report job triggered at {}", datetime.utcnow().isoformat())

    def _weekly_report_task(self) -> None:
        """Placeholder weekly report task until collectors are implemented."""

        logger.info("Weekly report job triggered at {}", datetime.utcnow().isoformat())

    def _monthly_report_task(self) -> None:
        """Placeholder monthly report task until collectors are implemented."""

        logger.info("Monthly report job triggered at {}", datetime.utcnow().isoformat())

    def _handle_job_event(self, event: JobExecutionEvent) -> None:
        """Log scheduler events for execution, failures, and missed runs."""

        if event.exception:
            logger.error("Job {} raised {}", event.job_id, event.exception)
            return
        if event.code == EVENT_JOB_MISSED:
            logger.warning("Job {} missed its run window", event.job_id)
            return
        logger.debug("Job {} completed successfully", event.job_id)


def create_job_manager() -> JobManager:
    """Create a configured scheduler job manager for application startup."""

    return JobManager()


class SchedulerService:
    """Compatibility wrapper around the APScheduler-backed job manager."""

    def __init__(self) -> None:
        """Initialize the compatibility wrapper."""

        self._manager = create_job_manager()

    def register_job(self, job_name: str) -> None:
        """Retain the legacy API by registering a placeholder named job."""

        self._manager.register_job(
            JobDefinition(name=job_name, func=self._manager._no_op_job, trigger=IntervalTrigger(minutes=30))
        )

    def start(self) -> list[str]:
        """Start the scheduler and return the current job identifiers."""

        self._manager.start()
        return [job["id"] for job in self._manager.list_jobs()]

    def pause_job(self, job_id: str) -> None:
        """Pause a specific scheduled job through the compatibility wrapper."""

        self._manager.pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        """Resume a specific scheduled job through the compatibility wrapper."""

        self._manager.resume_job(job_id)

    def pause_all(self) -> None:
        """Pause all scheduled jobs through the compatibility wrapper."""

        self._manager.pause_all()

    def resume_all(self) -> None:
        """Resume all scheduled jobs through the compatibility wrapper."""

        self._manager.resume_all()

    def shutdown(self) -> None:
        """Stop the scheduler through the compatibility wrapper."""

        self._manager.shutdown()

    def list_jobs(self) -> list[dict[str, str | None]]:
        """Return the current jobs through the compatibility wrapper."""

        return self._manager.list_jobs()

