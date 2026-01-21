"""SQLite-based cache manager for incremental builds."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ipodrb.models.plan import TrackJob, TrackResult


class CacheManager:
    """
    SQLite-based cache for tracking converted tracks.

    Cache key components:
    - Source path
    - Source mtime + size
    - Settings hash (action, bitrate, sample rate, tool version)

    Cache invalidation:
    - Source file changed (mtime/size)
    - Settings changed
    - Output file missing or unreadable
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS cache (
        source_path TEXT PRIMARY KEY,
        output_path TEXT NOT NULL,
        source_mtime REAL NOT NULL,
        source_size INTEGER NOT NULL,
        settings_hash TEXT NOT NULL,
        output_codec TEXT,
        output_sample_rate INTEGER,
        output_bit_depth INTEGER,
        output_size_bytes INTEGER,
        duration_seconds REAL,
        built_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_settings_hash ON cache(settings_hash);
    CREATE INDEX IF NOT EXISTS idx_output_path ON cache(output_path);
    """

    def __init__(self, db_path: Path):
        """
        Initialize cache manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def lookup(self, job: TrackJob) -> dict[str, Any] | None:
        """
        Look up cache entry for a job.

        Returns cached data if:
        - Entry exists
        - Source mtime and size match
        - Settings hash matches

        Args:
            job: Track job to look up

        Returns:
            Dict with cached data or None if not cached/invalid
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT output_path, source_mtime, source_size, settings_hash,
                       output_codec, output_sample_rate, output_bit_depth,
                       output_size_bytes, duration_seconds, built_at
                FROM cache
                WHERE source_path = ?
                """,
                (str(job.source_path),),
            )
            row = cursor.fetchone()

        if not row:
            return None

        (
            output_path,
            source_mtime,
            source_size,
            settings_hash,
            output_codec,
            output_sample_rate,
            output_bit_depth,
            output_size_bytes,
            duration_seconds,
            built_at,
        ) = row

        # Validate cache entry
        # Check source hasn't changed
        if abs(source_mtime - job.source_mtime) > 0.001:  # Allow small float diff
            return None
        if source_size != job.source_size:
            return None

        # Check settings match
        if settings_hash != job.settings_hash:
            return None

        # Check output path matches
        if output_path != str(job.output_path):
            return None

        return {
            "output_path": output_path,
            "output_codec": output_codec,
            "output_sample_rate": output_sample_rate,
            "output_bit_depth": output_bit_depth,
            "output_size_bytes": output_size_bytes,
            "duration_seconds": duration_seconds,
            "built_at": built_at,
        }

    def store(self, job: TrackJob, result: TrackResult) -> None:
        """
        Store successful conversion result in cache.

        Args:
            job: Track job that was processed
            result: Conversion result
        """
        if not result.success:
            return

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache
                (source_path, output_path, source_mtime, source_size, settings_hash,
                 output_codec, output_sample_rate, output_bit_depth,
                 output_size_bytes, duration_seconds, built_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(job.source_path),
                    str(job.output_path),
                    job.source_mtime,
                    job.source_size,
                    job.settings_hash,
                    result.output_codec,
                    result.output_sample_rate,
                    result.output_bit_depth,
                    result.output_size_bytes,
                    result.duration_seconds,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def invalidate(self, source_path: Path) -> None:
        """
        Remove cache entry for a source path.

        Args:
            source_path: Source file path to invalidate
        """
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM cache WHERE source_path = ?",
                (str(source_path),),
            )
            conn.commit()

    def invalidate_output(self, output_path: Path) -> None:
        """
        Remove cache entry by output path.

        Args:
            output_path: Output file path to invalidate
        """
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM cache WHERE output_path = ?",
                (str(output_path),),
            )
            conn.commit()

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def get_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dict with entry_count, total_size_bytes
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(output_size_bytes), 0)
                FROM cache
                """
            )
            count, total_size = cursor.fetchone()

        return {
            "entry_count": count,
            "total_size_bytes": total_size,
        }

    def prune_missing(self) -> int:
        """
        Remove cache entries where output file no longer exists.

        Returns:
            Number of entries removed
        """
        removed = 0

        with self._get_conn() as conn:
            cursor = conn.execute("SELECT source_path, output_path FROM cache")
            rows = cursor.fetchall()

            for source_path, output_path in rows:
                if not Path(output_path).exists():
                    conn.execute(
                        "DELETE FROM cache WHERE source_path = ?",
                        (source_path,),
                    )
                    removed += 1

            conn.commit()

        return removed
