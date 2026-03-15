import asyncio
import os
import time
from pathlib import Path
from typing import Optional


def ensure_temp_dir(path: Path) -> None:
    """
    Ensure the temporary directory used for session files exists.

    The directory is created with standard permissions and is intended
    for short-lived, per-session files only. It must not be used for
    permanent storage of DHS microdata.
    """

    path.mkdir(parents=True, exist_ok=True)


def _cleanup_expired_files(temp_dir: Path, ttl_seconds: int) -> None:
    """
    Remove files from `temp_dir` that are older than `ttl_seconds`.

    This function is intentionally conservative and will skip removal
    if any unexpected error occurs, to avoid impacting live sessions.
    """

    now = time.time()
    try:
        for entry in temp_dir.iterdir():
            try:
                if not entry.is_file():
                    continue
                mtime = os.path.getmtime(entry)
                if now - mtime > ttl_seconds:
                    entry.unlink(missing_ok=True)
            except OSError:
                # Best-effort cleanup; log in real implementation
                continue
    except FileNotFoundError:
        # Directory may have been removed between checks; ignore.
        return


def schedule_periodic_cleanup(
    temp_dir: Path,
    ttl_seconds: int,
    interval_seconds: Optional[int] = None,
) -> None:
    """
    Schedule periodic cleanup of expired temporary files.

    This is a cooperative background task using `asyncio`. It is
    designed to run for the lifetime of the FastAPI application.
    """

    interval = interval_seconds or max(ttl_seconds // 4, 60)

    async def _runner() -> None:
        while True:
            _cleanup_expired_files(temp_dir=temp_dir, ttl_seconds=ttl_seconds)
            await asyncio.sleep(interval)

    loop = asyncio.get_event_loop()
    loop.create_task(_runner())
