"""Logging: a configured stdlib logger plus a tiny append-only JSONL writer.

The JSONL writer backs the LLM call log and tool log described in
docs/ARCHITECTURE.md sections 4 and 6. One JSON object per line, append-only.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

_CONFIGURED = False


def get_logger(name: str = "adsb") -> logging.Logger:
    """Return a module logger, configuring the root handler once."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        _CONFIGURED = True
    return logging.getLogger(name)


class JsonlWriter:
    """Append-only JSON-lines writer. Creates parent directories as needed."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        record.setdefault("ts", time.time())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
