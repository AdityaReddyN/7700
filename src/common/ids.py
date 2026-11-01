"""Deterministic id and ref_id helpers.

ref_id formats follow docs/ARCHITECTURE.md section 3. Identical tool calls must
produce identical ref_ids, so the hash is taken over the canonical JSON of args.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid


def hash8(obj: object) -> str:
    """Stable 8-hex-char hash of any JSON-serialisable object."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def new_investigation_id(prefix: str = "inv") -> str:
    """Unique, time-sortable investigation id, e.g. ``inv_20260101T120000_ab12cd34``."""
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def alert_id(icao24: str, t_start: int, t_end: int) -> str:
    """Deterministic alert id from the aircraft and window."""
    return f"alert_{icao24}_{t_start}_{t_end}"


def ref_window(alert_id: str, t_start: int, t_end: int) -> str:
    return f"win:{alert_id}:{t_start}-{t_end}"


def ref_calc(alert_id: str, kind: str, args: dict) -> str:
    """calc ref_id for kinematics/baseline/identity. ``kind`` is e.g. kin|base|id."""
    return f"calc:{alert_id}:{kind}:{hash8(args)}"


def ref_case(card_id: str) -> str:
    return f"case:{card_id}"
