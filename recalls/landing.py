"""Raw landing zone: persist the exact feed bytes *before* parsing.

Why this matters for a real-time app: the source feeds are rolling windows --
old items scroll off and cannot be re-fetched. Landing the raw response means we
can replay / re-parse history if the parser improves or had a bug, and it is a
byte-for-byte audit trail of what each feed actually said. Deduped by content
hash, so a repeated (unchanged) window is not stored again.

A `Landing` port with a local-disk adapter now; a cloud/S3 adapter later is a new
class behind the same port -- same swap-the-backend philosophy as the store.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Protocol

from .config import Config

logger = logging.getLogger("recalls.landing")


class Landing(Protocol):
    def land(self, country: str, source: str, raw: bytes) -> bool:
        """Persist raw feed bytes; return True if stored, False if skipped
        (unchanged since the last landing for this country/source)."""
        ...


class NullLanding:
    """No-op landing (for tests or when landing is disabled)."""

    def land(self, country: str, source: str, raw: bytes) -> bool:
        return False


class LocalDirLanding:
    """Land raw bytes as gzipped files on local disk, deduped by content hash.

    Layout: ``<root>/<country>/<source>/<UTC-timestamp>-<sha8>.xml.gz`` plus a
    ``.last_sha256`` marker used to skip an unchanged repeat.
    """

    def __init__(self, root: str) -> None:
        self._root = root

    def land(self, country: str, source: str, raw: bytes) -> bool:
        digest = hashlib.sha256(raw).hexdigest()
        directory = os.path.join(self._root, country, source)
        os.makedirs(directory, exist_ok=True)

        marker = os.path.join(directory, ".last_sha256")
        try:
            with open(marker) as fh:
                if fh.read().strip() == digest:
                    logger.info(
                        "landing skip country=%s source=%s (unchanged)", country, source
                    )
                    return False
        except FileNotFoundError:
            pass

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(directory, f"{ts}-{digest[:8]}.xml.gz")
        with gzip.open(path, "wb") as fh:
            fh.write(raw)
        with open(marker, "w") as fh:
            fh.write(digest)
        logger.info(
            "landed country=%s source=%s bytes=%s path=%s", country, source, len(raw), path
        )
        return True


def open_landing(config: Config) -> Landing:
    """The configured landing backend (local disk today)."""
    return LocalDirLanding(config.landing_dir)
