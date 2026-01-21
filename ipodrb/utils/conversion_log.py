"""Conversion log output for tracking build results."""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ipodrb.models.plan import TrackJob, TrackResult


@dataclass
class ConversionLogEntry:
    """Single track conversion log entry."""

    timestamp: str
    album_id: str
    source_path: str
    output_path: str
    action: str
    source_format: str
    source_sample_rate: int
    source_bit_depth: int | None
    target_codec: str
    target_sample_rate: int
    target_bit_depth: int | None
    aac_bitrate: int | None
    dither_applied: bool
    success: bool
    error_code: str | None = None
    error_message: str | None = None
    duration_seconds: float | None = None
    output_size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "album_id": self.album_id,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "action": self.action,
            "source_format": self.source_format,
            "source_sample_rate": self.source_sample_rate,
            "source_bit_depth": self.source_bit_depth,
            "target_codec": self.target_codec,
            "target_sample_rate": self.target_sample_rate,
            "target_bit_depth": self.target_bit_depth,
            "aac_bitrate_kbps": self.aac_bitrate,
            "dither_applied": self.dither_applied,
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "output_size_bytes": self.output_size_bytes,
        }


@dataclass
class ConversionSummary:
    """Summary statistics for a conversion run."""

    started_at: datetime
    completed_at: datetime | None = None
    total_tracks: int = 0
    succeeded: int = 0
    failed: int = 0
    cached: int = 0
    total_source_bytes: int = 0
    total_output_bytes: int = 0
    albums_processed: int = 0
    albums_skipped: int = 0

    @property
    def duration_seconds(self) -> float:
        """Total run duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0

    @property
    def compression_ratio(self) -> float:
        """Output size / source size ratio."""
        if self.total_source_bytes > 0:
            return self.total_output_bytes / self.total_source_bytes
        return 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "total_tracks": self.total_tracks,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "cached": self.cached,
            "total_source_bytes": self.total_source_bytes,
            "total_output_bytes": self.total_output_bytes,
            "compression_ratio": round(self.compression_ratio, 3),
            "albums_processed": self.albums_processed,
            "albums_skipped": self.albums_skipped,
        }


@dataclass
class ConversionLog:
    """Tracks all conversions and writes logs to output folder."""

    output_root: Path
    entries: list[ConversionLogEntry] = field(default_factory=list)
    summary: ConversionSummary = field(default_factory=lambda: ConversionSummary(started_at=datetime.now()))
    errors: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self.output_root = Path(self.output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def start(self, total_tracks: int, albums_processed: int, albums_skipped: int) -> None:
        """Mark the start of conversion run."""
        self.summary = ConversionSummary(
            started_at=datetime.now(),
            total_tracks=total_tracks,
            albums_processed=albums_processed,
            albums_skipped=albums_skipped,
        )

    def log_track(self, job: TrackJob, result: TrackResult) -> None:
        """Log a single track conversion."""
        # Extract source format from path
        source_format = job.source_path.suffix.upper().lstrip(".")

        entry = ConversionLogEntry(
            timestamp=datetime.now().isoformat(),
            album_id=job.album_id,
            source_path=str(job.source_path),
            output_path=str(job.output_path),
            action=job.action.value,
            source_format=source_format,
            source_sample_rate=job.source_path.stat().st_size if hasattr(job, "source_sample_rate") else 0,
            source_bit_depth=getattr(job, "source_bit_depth", None),
            target_codec=job.target_codec,
            target_sample_rate=job.target_sample_rate,
            target_bit_depth=job.target_bit_depth,
            aac_bitrate=job.aac_bitrate_kbps,
            dither_applied=job.apply_dither,
            success=result.success,
            error_code=result.error_code if hasattr(result, "error_code") else None,
            error_message=result.error_message if hasattr(result, "error_message") else None,
            duration_seconds=result.duration_seconds if hasattr(result, "duration_seconds") else None,
            output_size_bytes=result.output_size_bytes if hasattr(result, "output_size_bytes") else None,
        )

        self.entries.append(entry)

        # Update summary
        if result.success:
            self.summary.succeeded += 1
            if hasattr(result, "output_size_bytes") and result.output_size_bytes:
                self.summary.total_output_bytes += result.output_size_bytes
        else:
            self.summary.failed += 1
            self.errors.append({
                "album_id": job.album_id,
                "source_path": str(job.source_path),
                "error_code": getattr(result, "error_code", "UNKNOWN"),
                "error_message": getattr(result, "error_message", "Unknown error"),
            })

        self.summary.total_source_bytes += job.source_size

    def log_cached(self, job: TrackJob) -> None:
        """Log a cached (skipped) track."""
        self.summary.cached += 1

    def complete(self) -> None:
        """Mark conversion run as complete."""
        self.summary.completed_at = datetime.now()

    def write_logs(self) -> dict[str, Path]:
        """
        Write all log files to output directory.

        Returns dict mapping log type to path.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = self.output_root / ".logs"
        log_dir.mkdir(exist_ok=True)

        paths = {}

        # Write human-readable summary
        summary_path = log_dir / f"conversion_summary_{timestamp}.txt"
        self._write_summary_txt(summary_path)
        paths["summary"] = summary_path

        # Write CSV manifest
        manifest_path = self.output_root / "manifest.csv"
        self._write_manifest_csv(manifest_path)
        paths["manifest"] = manifest_path

        # Write JSONL detailed log
        jsonl_path = log_dir / f"conversion_log_{timestamp}.jsonl"
        self._write_jsonl(jsonl_path)
        paths["jsonl"] = jsonl_path

        # Write JSON summary
        json_path = log_dir / f"conversion_summary_{timestamp}.json"
        self._write_summary_json(json_path)
        paths["json"] = json_path

        # Write errors log if any
        if self.errors:
            errors_path = log_dir / f"errors_{timestamp}.txt"
            self._write_errors(errors_path)
            paths["errors"] = errors_path

        return paths

    def _write_summary_txt(self, path: Path) -> None:
        """Write human-readable summary."""
        with open(path, "w") as f:
            f.write("=" * 60 + "\n")
            f.write("CONVERSION SUMMARY\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Started:    {self.summary.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
            if self.summary.completed_at:
                f.write(f"Completed:  {self.summary.completed_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Duration:   {self.summary.duration_seconds:.1f} seconds\n")
            f.write("\n")

            f.write("RESULTS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total tracks:     {self.summary.total_tracks}\n")
            f.write(f"Succeeded:        {self.summary.succeeded}\n")
            f.write(f"Failed:           {self.summary.failed}\n")
            f.write(f"Cached (skipped): {self.summary.cached}\n")
            f.write("\n")

            f.write("ALBUMS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Processed:  {self.summary.albums_processed}\n")
            f.write(f"Skipped:    {self.summary.albums_skipped}\n")
            f.write("\n")

            f.write("SIZE\n")
            f.write("-" * 40 + "\n")
            source_mb = self.summary.total_source_bytes / (1024 * 1024)
            output_mb = self.summary.total_output_bytes / (1024 * 1024)
            f.write(f"Source size:  {source_mb:.1f} MB\n")
            f.write(f"Output size:  {output_mb:.1f} MB\n")
            if self.summary.compression_ratio > 0:
                f.write(f"Compression:  {self.summary.compression_ratio:.1%}\n")
            f.write("\n")

            if self.errors:
                f.write("ERRORS\n")
                f.write("-" * 40 + "\n")
                for err in self.errors[:20]:  # Show first 20 errors
                    f.write(f"  [{err.get('error_code', 'ERROR')}] {err.get('source_path', 'Unknown')}\n")
                    if err.get("error_message"):
                        f.write(f"    {err['error_message'][:80]}\n")
                if len(self.errors) > 20:
                    f.write(f"  ... and {len(self.errors) - 20} more errors\n")

    def _write_manifest_csv(self, path: Path) -> None:
        """Write CSV manifest of all converted tracks."""
        fieldnames = [
            "album_id",
            "source_path",
            "output_path",
            "action",
            "target_codec",
            "target_sample_rate",
            "target_bit_depth",
            "aac_bitrate_kbps",
            "dither_applied",
            "success",
            "error_code",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(entry.to_dict())

    def _write_jsonl(self, path: Path) -> None:
        """Write JSONL detailed log."""
        with open(path, "w") as f:
            # Write summary as first line
            f.write(json.dumps({"type": "summary", "data": self.summary.to_dict()}) + "\n")

            # Write each entry
            for entry in self.entries:
                f.write(json.dumps({"type": "track", "data": entry.to_dict()}) + "\n")

    def _write_summary_json(self, path: Path) -> None:
        """Write JSON summary."""
        data = {
            "summary": self.summary.to_dict(),
            "errors": self.errors,
            "action_counts": self._count_actions(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _write_errors(self, path: Path) -> None:
        """Write errors to text file."""
        with open(path, "w") as f:
            f.write("CONVERSION ERRORS\n")
            f.write("=" * 60 + "\n\n")
            for err in self.errors:
                f.write(f"Album: {err.get('album_id', 'Unknown')}\n")
                f.write(f"File:  {err.get('source_path', 'Unknown')}\n")
                f.write(f"Code:  {err.get('error_code', 'UNKNOWN')}\n")
                f.write(f"Error: {err.get('error_message', 'No message')}\n")
                f.write("-" * 40 + "\n")

    def _count_actions(self) -> dict[str, int]:
        """Count tracks by action type."""
        counts: dict[str, int] = {}
        for entry in self.entries:
            action = entry.action
            counts[action] = counts.get(action, 0) + 1
        return counts
