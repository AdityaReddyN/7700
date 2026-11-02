"""M5: the tool registry (ARCHITECTURE §3).

Binds one alert to its track provider, case retriever and ToolLog, then
dispatches `call(name, args)` to the matching tool and records the result. The
model-facing (truncated) `ToolResult` is returned; the full output stays in the
ToolLog for the verifier. The OpenAI specs shown to the model are imported from
`agents.tool_specs` (unchanged since M1), so there is one source of truth.
"""

from __future__ import annotations

from pathlib import Path

from agents.tool_specs import TOOL_NAMES, TOOL_SPECS
from common.config import REPO_ROOT, get_settings, load_yaml
from common.schemas import Alert, ToolResult
from tools import data_tools as dt
from tools.retrieval import CaseRetriever, retrieve_cases
from tools.toollog import ToolLog

__all__ = ["ToolRegistry", "TOOL_SPECS", "TOOL_NAMES", "default_provider"]

_WINDOW_TOOLS = {
    "get_track_window": dt.get_track_window,
    "compute_kinematics": dt.compute_kinematics,
    "check_identity": dt.check_identity,
}


def _max_chars() -> int:
    try:
        return int(load_yaml("agents").get("tool_output_max_chars", 1600))
    except FileNotFoundError:
        return 1600


class ToolRegistry:
    """Per-investigation tool dispatch. One registry per alert."""

    def __init__(self, alert: Alert, provider: dt.TrackProvider,
                 retriever: CaseRetriever | None = None, log: ToolLog | None = None) -> None:
        self.alert = alert
        self.provider = provider
        self.retriever = retriever
        self.log = log or ToolLog(max_chars=_max_chars())

    def call(self, name: str, args: dict) -> ToolResult:
        if name not in TOOL_NAMES:
            raise ValueError(f"unknown tool: {name}")
        args = dict(args or {})
        aid = self.alert.alert_id

        if name == "retrieve_cases":
            output, ref_id, extra = retrieve_cases(
                self.retriever, aid,
                query=str(args.get("query", "")),
                hypothesis=str(args.get("hypothesis", "")),
                k=int(args.get("k", 4)),
            )
            for eid, eout in extra:
                self.log.record(name, args, eout, eid)
        elif name == "compare_to_baseline":
            output, ref_id = dt.compare_to_baseline(
                self.provider, aid,
                alert_icao24=self.alert.icao24,
                alert_t_start=self.alert.t_start,
                alert_t_end=self.alert.t_end,
                feature=str(args["feature"]),
                context=str(args.get("context", "all")),
            )
        else:
            fn = _WINDOW_TOOLS[name]
            output, ref_id = fn(
                self.provider, aid,
                icao24=str(args["icao24"]),
                t_start=int(args["t_start"]),
                t_end=int(args["t_end"]),
            )
        return self.log.record(name, args, output, ref_id)


def default_provider() -> dt.TrackProvider:
    """Build a provider over the real store + the scenario view (for live runs)."""
    import json

    import pandas as pd

    from scenarios.select import connect

    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    scen = data_dir / "scenarios"
    tracks_path = scen / "tracks.parquet"
    tracks = pd.read_parquet(tracks_path) if tracks_path.exists() else None
    exclude: set[str] = set()
    cat = scen / "splits.json"
    if cat.exists():
        catalog = json.loads(cat.read_text(encoding="utf-8"))
        exclude = {str(s["icao24"]) for s in catalog["scenarios"]}
    return dt.TrackProvider(con=connect(), scenario_tracks=tracks, exclude_icao24=exclude)


def default_retriever() -> CaseRetriever:
    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    return CaseRetriever.from_kb(Path(data_dir) / "kb")
