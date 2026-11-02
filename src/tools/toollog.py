"""M5: the ToolLog (ARCHITECTURE §4).

One ToolLog per investigation. It keeps the full, untruncated output of every
tool call keyed by `ref_id` so the verifier can check cited values, and hands
the model a view truncated to the configured size. Identical calls (same
`ref_id`) are recorded once and returned from cache, so the model and the trace
stay consistent and cheap.
"""

from __future__ import annotations

import json
import time

from common.schemas import ToolResult

_DEFAULT_MAX_CHARS = 1600  # ~400 tokens (ARCHITECTURE §3 size rule)


def _json_len(output: dict) -> int:
    return len(json.dumps(output, sort_keys=True, separators=(",", ":"), default=str))


def truncate_output(output: dict, max_chars: int) -> tuple[dict, bool]:
    """Shrink the serialised output under max_chars by trimming its longest list.

    Flat scalar outputs are never altered; only list-valued fields are cut, which
    is what the bounded tools (e.g. retrieve_cases) need. Returns (output, cut?).
    """
    if _json_len(output) <= max_chars:
        return output, False
    out = dict(output)
    cut = False
    # Repeatedly halve the longest remaining list until we fit or cannot shrink.
    while _json_len(out) > max_chars:
        lists = [(k, v) for k, v in out.items() if isinstance(v, list) and len(v) > 0]
        if not lists:
            break
        key, val = max(lists, key=lambda kv: len(kv[1]))
        keep = max(1, len(val) // 2)
        if keep == len(val):
            break
        out[key] = val[:keep]
        cut = True
    return out, cut


class ToolLog:
    def __init__(self, max_chars: int = _DEFAULT_MAX_CHARS) -> None:
        self._full: dict[str, ToolResult] = {}   # untruncated, for the verifier
        self._view: dict[str, ToolResult] = {}    # truncated, for the model
        self.max_chars = max_chars

    def __contains__(self, ref_id: str) -> bool:
        return ref_id in self._full

    def __len__(self) -> int:
        return len(self._full)

    def record(self, tool: str, args: dict, output: dict, ref_id: str) -> ToolResult:
        """Record a call and return the model-facing (truncated) result.

        A repeated ref_id returns the cached view without recomputing anything.
        """
        if ref_id in self._view:
            return self._view[ref_id]
        ts = time.time()
        self._full[ref_id] = ToolResult(
            ref_id=ref_id, tool=tool, args=args, output=output, truncated=False, ts=ts
        )
        view_output, cut = truncate_output(output, self.max_chars)
        view = ToolResult(
            ref_id=ref_id, tool=tool, args=args, output=view_output, truncated=cut, ts=ts
        )
        self._view[ref_id] = view
        return view

    def get_full(self, ref_id: str) -> ToolResult | None:
        """Full, untruncated result for the verifier."""
        return self._full.get(ref_id)

    def as_dict(self) -> dict[str, dict]:
        """Full log for the saved trace: ref_id -> serialised ToolResult."""
        return {ref_id: res.model_dump() for ref_id, res in self._full.items()}
