"""M3: leakage checks (pure functions) used by tests/test_leakage.py.

No test-split information may reach the knowledge base, prompts, tool outputs or
alert objects (AGENTS non-negotiable #2). These functions operate on the
scenario catalog and on-disk artifacts and return a list of violation strings;
empty means clean. They are hermetically testable on synthetic catalogs.
"""

from __future__ import annotations

import re
from pathlib import Path

_SID_RE = re.compile(r"\bS\d{4}\b")


def check_hour_groups_disjoint(groups: dict[str, list[int]]) -> list[str]:
    violations = []
    names = list(groups)
    for a_i in range(len(names)):
        for b_i in range(a_i + 1, len(names)):
            overlap = set(groups[names[a_i]]) & set(groups[names[b_i]])
            if overlap:
                violations.append(
                    f"hour groups {names[a_i]}/{names[b_i]} overlap: {sorted(overlap)}"
                )
    return violations


def _hour_of(ts: int) -> int:
    # Seconds since 2019-12-09 00:00:00 UTC -> hour of day.
    return (ts - 1575849600) // 3600


def check_cross_split_overlap(scenarios: list[dict]) -> list[str]:
    """Test windows must not share an aircraft+time overlap with kb/dev scenarios."""
    violations = []
    test = [s for s in scenarios if s["split"] == "test"]
    other = [s for s in scenarios if s["split"] in ("kb", "dev")]
    for ts in test:
        for os_ in other:
            if ts["icao24"] == os_["icao24"] and not (
                ts["t_end"] < os_["t_start"] or ts["t_start"] > os_["t_end"]
            ):
                violations.append(
                    f"{ts['scenario_id']} (test) overlaps {os_['scenario_id']} "
                    f"({os_['split']}) on {ts['icao24']}"
                )
    return violations


def check_source_windows_in_group(scenarios: list[dict], groups: dict[str, list[int]]) -> list[str]:
    """A replay source window must stay within the scenario's own split hours."""
    violations = []
    for s in scenarios:
        sw = s.get("params", {}).get("source_window")
        if not sw:
            continue
        allowed = set(groups[s["split"]])
        hours = {_hour_of(sw[0]), _hour_of(sw[1])}
        if not hours <= allowed:
            violations.append(
                f"{s['scenario_id']} replay source window hours {sorted(hours)} "
                f"outside {s['split']} group"
            )
    return violations


def check_no_test_ids_in_kb(kb_dir: Path, test_ids: set[str]) -> list[str]:
    violations = []
    if not kb_dir.exists():
        return violations
    for path in kb_dir.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json", ".txt", ".jsonl"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            found = {sid for sid in _SID_RE.findall(text) if sid in test_ids}
            if found:
                violations.append(f"{path.name} contains test scenario ids {sorted(found)}")
    return violations


def check_tracks_no_label(columns: list[str]) -> list[str]:
    return ["tracks.parquet has a 'label' column"] if "label" in columns else []


def check_alert_schema_no_label() -> list[str]:
    from common.schemas import Alert

    return ["Alert schema exposes a 'label' field"] if "label" in Alert.model_fields else []


def run_all(catalog: dict, *, kb_dir: Path, tracks_columns: list[str]) -> list[str]:
    scenarios = catalog["scenarios"]
    groups = catalog["hour_groups"]
    test_ids = {s["scenario_id"] for s in scenarios if s["split"] == "test"}
    violations: list[str] = []
    violations += check_hour_groups_disjoint(groups)
    violations += check_cross_split_overlap(scenarios)
    violations += check_source_windows_in_group(scenarios, groups)
    violations += check_no_test_ids_in_kb(kb_dir, test_ids)
    violations += check_tracks_no_label(tracks_columns)
    violations += check_alert_schema_no_label()
    return violations
