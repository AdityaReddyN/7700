"""M2: write the data report from the Parquet store and the convert manifest.

Reads the manifest (row counts and null counts before/after cleaning, file
checksums) and queries the Parquet store read-only with DuckDB (coverage,
aircraft counts, snapshots per aircraft, flag shares). Writes
`results/data_report/report.md` and `summary.json`. Every number is computed
here, never hand-typed (AGENTS non-negotiable #3).

Run: `python -m data.report` (Makefile `report`).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from common.config import REPO_ROOT, get_settings
from common.logging import get_logger
from common.schemas import LABELS  # noqa: F401  (kept for cross-ref; unused here)

log = get_logger("data.report")

ATTRIBUTION = (
    "Data: The OpenSky Network (https://opensky-network.org). Used under the "
    "OpenSky General Terms of Use & Data License Agreement (bundled LICENSE.txt "
    "in each raw archive). Permission for this hackathon use is recorded in "
    "docs/permissions/G2-opensky.md (gate G2); follow any conditions stated there. "
    "Raw data is not redistributed in this repository."
)


def _utc(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _agg_nulls(hours: list[dict], key: str, columns: list[str]) -> dict[str, int]:
    return {c: sum(h[key][c] for h in hours) for c in columns}


def build_summary(manifest: dict, parquet_glob: str) -> dict:
    hours = manifest["hours"]
    columns = manifest["columns"]
    rows_in = sum(h["rows_in"] for h in hours)
    rows_after = sum(h["rows_after"] for h in hours)
    null_before = _agg_nulls(hours, "null_before", columns)
    null_after = _agg_nulls(hours, "null_after", columns)

    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=2")
    rel = f"read_parquet('{parquet_glob}', hive_partitioning=1)"
    total, aircraft, t_min, t_max = con.execute(
        f"SELECT count(*), count(DISTINCT icao24), min(time), max(time) FROM {rel}"
    ).fetchone()
    median_snaps = con.execute(
        f"SELECT median(c) FROM (SELECT icao24, count(*) c FROM {rel} GROUP BY icao24)"
    ).fetchone()[0]
    onground, alert, spi = con.execute(
        f"SELECT avg(CAST(onground AS INT)), avg(CAST(alert AS INT)), "
        f"avg(CAST(spi AS INT)) FROM {rel}"
    ).fetchone()
    per_hour = con.execute(
        f'SELECT hour, count(*) AS n_rows, count(DISTINCT icao24) AS n_aircraft '
        f"FROM {rel} GROUP BY hour ORDER BY hour"
    ).fetchall()
    con.close()

    return {
        "date": manifest["date"],
        "n_hours": manifest["n_hours"],
        "files": [
            {"source": Path(h["source"]).name, "sha256": h["sha256"],
             "bytes": h["source_bytes"], "hour": h["hour"]}
            for h in hours
        ],
        "coverage": {
            "t_min": t_min, "t_max": t_max,
            "t_min_utc": _utc(t_min), "t_max_utc": _utc(t_max),
            "span_seconds": (t_max - t_min) if (t_min is not None and t_max is not None) else None,
        },
        "rows": {
            "before_cleaning": rows_in,
            "after_cleaning": int(total),
            "rejected": rows_in - rows_after,
            "note": "cleaning drops only rows missing icao24 or time (DATA_SPEC §4)",
        },
        "aircraft_total": int(aircraft),
        "median_snapshots_per_aircraft": float(median_snaps) if median_snaps is not None else None,
        "null_rate_before": {c: round(null_before[c] / rows_in, 4) if rows_in else None
                             for c in columns},
        "null_rate_after": {c: round(null_after[c] / rows_after, 4) if rows_after else None
                            for c in columns},
        "flag_share": {
            "onground": round(onground, 4) if onground is not None else None,
            "alert": round(alert, 4) if alert is not None else None,
            "spi": round(spi, 4) if spi is not None else None,
            "note": "reported only; alert and spi are never used as features (DATA_SPEC §3)",
        },
        "per_hour": [{"hour": int(h), "rows": int(r), "aircraft": int(a)} for h, r, a in per_hour],
        "attribution": ATTRIBUTION,
    }


def render_md(s: dict) -> str:
    cov = s["coverage"]
    lines = [
        f"# Data report — {s['date']}",
        "",
        "> One day of OpenSky traffic (2019-12-09), not representative of all traffic. "
        "A single day; the scenario split uses the hour-based fallback (D-029).",
        "",
        "## Coverage",
        f"- Hours: {s['n_hours']}",
        f"- Time span: {cov['t_min_utc']} to {cov['t_max_utc']} "
        f"({cov['span_seconds']} s)",
        "",
        "## Rows",
        f"- Before cleaning: {s['rows']['before_cleaning']:,}",
        f"- After cleaning: {s['rows']['after_cleaning']:,}",
        f"- Rejected (missing icao24 or time): {s['rows']['rejected']:,}",
        "",
        "## Aircraft",
        f"- Distinct aircraft: {s['aircraft_total']:,}",
        f"- Median snapshots per aircraft: {s['median_snapshots_per_aircraft']}",
        "",
        "## Flag share (reported, not used as features)",
        f"- onground: {s['flag_share']['onground']}",
        f"- alert: {s['flag_share']['alert']}",
        f"- spi: {s['flag_share']['spi']}",
        "",
        "## Null rate after cleaning (by column)",
    ]
    for col, rate in s["null_rate_after"].items():
        lines.append(f"- {col}: {rate}")
    lines += [
        "",
        "## Rows and aircraft per hour",
        "",
        "| hour | rows | aircraft |",
        "|---|---|---|",
    ]
    lines += [f"| {h['hour']:02d} | {h['rows']:,} | {h['aircraft']:,} |" for h in s["per_hour"]]
    lines += [
        "",
        "## Files (SHA-256)",
        "",
        "| hour | file | bytes | sha256 |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {f['hour']:02d} | {f['source']} | {f['bytes']:,} | `{f['sha256'][:16]}…` |"
        for f in s["files"]
    ]
    lines += ["", "## Attribution", "", s["attribution"], ""]
    return "\n".join(lines)


def write_report(manifest_path: Path, parquet_glob: str, out_dir: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = build_summary(manifest, parquet_glob)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_md(summary), encoding="utf-8")
    log.info("wrote report for %d rows, %d aircraft",
             summary["rows"]["after_cleaning"], summary["aircraft_total"])
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Write the M2 data report.")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--parquet-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    report_dir = REPO_ROOT / "results" / "data_report"
    manifest_path = Path(args.manifest) if args.manifest else report_dir / "convert_manifest.json"
    parquet_dir = Path(args.parquet_dir) if args.parquet_dir else data_dir / "parquet"
    out_dir = Path(args.out_dir) if args.out_dir else report_dir
    glob = str(parquet_dir / "states" / "**" / "*.parquet").replace("\\", "/")
    write_report(manifest_path, glob, out_dir)


if __name__ == "__main__":
    main()
