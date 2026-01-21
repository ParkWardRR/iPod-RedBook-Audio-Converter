"""Parallel conversion pipeline."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from ipodrb.cache.manager import CacheManager
from ipodrb.converter.transcoder import convert_track
from ipodrb.models.config import ApplyConfig, Config
from ipodrb.models.plan import BuildPlan, TrackJob, TrackResult
from ipodrb.utils.conversion_log import ConversionLog


@dataclass
class PipelineEvent:
    """Base event for pipeline progress."""

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class JobStartedEvent(PipelineEvent):
    """Event when a job starts processing."""

    job: TrackJob | None = None


@dataclass
class JobCompletedEvent(PipelineEvent):
    """Event when a job completes."""

    job: TrackJob | None = None
    result: TrackResult | None = None


@dataclass
class JobErrorEvent(PipelineEvent):
    """Event when a job fails."""

    job: TrackJob | None = None
    error: str = ""


@dataclass
class PipelineStats:
    """Statistics for pipeline execution."""

    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cached_jobs: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def in_progress(self) -> int:
        return self.total_jobs - self.completed_jobs - self.failed_jobs - self.cached_jobs


class ConversionPipeline:
    """
    Parallel conversion pipeline using ProcessPoolExecutor.

    Handles:
    - Cache checking to skip already-converted tracks
    - Parallel execution across CPU cores
    - Progress events for TUI updates
    - Error collection and reporting
    """

    def __init__(
        self,
        config: ApplyConfig,
        global_config: Config | None = None,
        event_callback: Callable[[PipelineEvent], None] | None = None,
    ):
        self.config = config
        self.global_config = global_config or Config()
        self.event_callback = event_callback
        self.cache = CacheManager(config.output_root / config.cache_db_name)
        self.stats = PipelineStats()
        self.conversion_log = ConversionLog(config.output_root)

    def emit(self, event: PipelineEvent) -> None:
        """Emit event to callback if registered."""
        if self.event_callback:
            self.event_callback(event)

    def execute(
        self,
        plan: BuildPlan,
        dry_run: bool = False,
    ) -> list[TrackResult]:
        """
        Execute the build plan.

        Args:
            plan: Build plan with all jobs
            dry_run: If True, only report what would be done

        Returns:
            List of TrackResult for all processed jobs
        """
        self.stats = PipelineStats(
            total_jobs=len(plan.jobs),
            started_at=datetime.now(),
        )

        # Initialize conversion log
        self.conversion_log = ConversionLog(self.config.output_root)
        self.conversion_log.start(
            total_tracks=len(plan.jobs),
            albums_processed=len(set(j.album_id for j in plan.jobs)),
            albums_skipped=len(plan.skipped_albums),
        )

        if dry_run:
            return self._dry_run(plan)

        # Filter out cached jobs
        jobs_to_run = []
        cached_results = []

        for job in plan.jobs:
            if not self.config.force and self._is_cached(job):
                self.stats.cached_jobs += 1
                self.conversion_log.log_cached(job)
                cached_results.append(TrackResult(
                    source_path=job.source_path,
                    output_path=job.output_path,
                    success=True,
                ))
            else:
                jobs_to_run.append(job)

        # Execute remaining jobs in parallel
        results = cached_results.copy()

        if jobs_to_run:
            results.extend(self._run_parallel(jobs_to_run))

        self.stats.completed_at = datetime.now()

        # Complete and write conversion logs
        self.conversion_log.complete()
        log_paths = self.conversion_log.write_logs()

        return results

    def _is_cached(self, job: TrackJob) -> bool:
        """Check if job output is cached and valid."""
        if not job.output_path.exists():
            return False

        cached = self.cache.lookup(job)
        if not cached:
            return False

        # Verify output still exists and is readable
        try:
            if job.output_path.stat().st_size == 0:
                return False
        except OSError:
            return False

        return True

    def _run_parallel(self, jobs: list[TrackJob]) -> list[TrackResult]:
        """Run jobs in parallel using process pool."""
        results = []

        # We use ProcessPoolExecutor for CPU-bound encoding
        # But convert_track needs to be picklable, so we pass simple args
        with ProcessPoolExecutor(max_workers=self.config.threads) as executor:
            # Submit all jobs
            future_to_job = {}
            for job in jobs:
                self.emit(JobStartedEvent(job=job))
                future = executor.submit(
                    _convert_track_worker,
                    job,
                    self.global_config,
                )
                future_to_job[future] = job

            # Collect results
            for future in as_completed(future_to_job):
                job = future_to_job[future]

                try:
                    result = future.result()

                    if result.success:
                        self.stats.completed_jobs += 1
                        # Update cache
                        self.cache.store(job, result)
                        self.emit(JobCompletedEvent(job=job, result=result))
                    else:
                        self.stats.failed_jobs += 1
                        self.emit(JobErrorEvent(
                            job=job,
                            error=result.error_message or "Unknown error",
                        ))

                    # Log the track conversion
                    self.conversion_log.log_track(job, result)
                    results.append(result)

                except Exception as e:
                    self.stats.failed_jobs += 1
                    error_result = TrackResult(
                        source_path=job.source_path,
                        success=False,
                        error_message=str(e),
                    )
                    # Log the error
                    self.conversion_log.log_track(job, error_result)
                    results.append(error_result)
                    self.emit(JobErrorEvent(job=job, error=str(e)))

                    if self.config.fail_fast:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

        return results

    def _dry_run(self, plan: BuildPlan) -> list[TrackResult]:
        """Report what would be done without actually doing it."""
        results = []
        for job in plan.jobs:
            cached = self._is_cached(job)
            results.append(TrackResult(
                source_path=job.source_path,
                output_path=job.output_path,
                success=True,
            ))
            if cached:
                self.stats.cached_jobs += 1
            else:
                self.stats.completed_jobs += 1
        return results


def _convert_track_worker(job: TrackJob, config: Config) -> TrackResult:
    """
    Worker function for process pool.

    This runs in a separate process, so it must be a module-level function.
    """
    return convert_track(job, config)
