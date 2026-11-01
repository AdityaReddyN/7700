"""M2: convert OpenSky hourly files to a partitioned Parquet store.

Each raw file is a tar containing a gzipped CSV plus OpenSky's LICENSE/README
(see DATA_SPEC §2). This module, per hour: untar -> gunzip -> pandas (typed) ->
clean (DATA_SPEC §4) -> write Parquet partitioned by date/hour, sorted by
icao24 then time. It also emits a conversion manifest with the before/after
row counts and null counts the data report needs.

Raw data is never modified. Run: `python -m data.convert` (Makefile `data`).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tarfile
from pathlib import Path

import pandas as pd

from common.config import REPO_ROOT, get_settings
from common.logging import get_logger

log = get_logger("data.convert")

EXPECTED_COLUMNS: list[str] = [
    "time", "icao24", "lat", "lon", "velocity", "heading", "vertrate",
    "callsign", "onground", "alert", "spi", "squawk",
    "baroaltitude", "geoaltitude", "lastposupdate", "lastcontact",
]
_STR_COLS = ["icao24", "callsign", "squawk"]
_BOOL_COLS = ["onground", "alert", "spi"]
_FLOAT_COLS = [
    "lat", "lon", "velocity", "heading", "vertrate",
    "baroaltitude", "geoaltitude", "lastposupdate", "lastcontact",
]
_HOUR_RE = re.compile(r"states_(\d{4}-\d{2}-\d{2})-(\d{2})\.csv\.tar$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_hour_files(raw_dir: Path) -> dict[int, Path]:
    """Map hour -> tar path for one day's folder (handles the hidden dotfolder)."""
    files: dict[int, Path] = {}
    for p in sorted(raw_dir.rglob("states_*-*.csv.tar")):
        m = _HOUR_RE.search(p.name)
        if m:
            files[int(m.group(2))] = p
    return files


def read_hour(tar_path: Path, nrows: int | None = None) -> pd.DataFrame:
    """tar -> gzipped CSV member -> typed DataFrame. Validates the header."""
    with tarfile.open(tar_path) as tf:
        gz_name = next((m.name for m in tf.getmembers() if m.name.endswith(".csv.gz")), None)
        if gz_name is None:
            raise ValueError(f"no .csv.gz member in {tar_path}")
        member = tf.extractfile(gz_name)
        with gzip.GzipFile(fileobj=member) as csv_stream:
            df = pd.read_csv(
                csv_stream,
                nrows=nrows,
                dtype={c: "string" for c in _STR_COLS},
                na_values=[""],
                keep_default_na=True,
                low_memory=False,
            )
    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            f"unexpected header in {tar_path.name}: {list(df.columns)} "
            f"(expected {EXPECTED_COLUMNS}). Log the difference before converting."
        )
    # Typed coercion.
    df["time"] = pd.to_numeric(df["time"], errors="coerce").astype("Int64")
    for c in _FLOAT_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    _bool_map = {"True": True, "False": False, True: True, False: False}
    for c in _BOOL_COLS:
        df[c] = df[c].map(_bool_map).astype("boolean")
    df["callsign"] = df["callsign"].str.strip().replace("", pd.NA)
    return df


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """DATA_SPEC §4: drop rows missing icao24 or time; keep feature-null rows."""
    rows_in = len(df)
    null_before = {c: int(df[c].isna().sum()) for c in EXPECTED_COLUMNS}
    keep = df["icao24"].notna() & (df["icao24"].str.len() > 0) & df["time"].notna()
    out = df.loc[keep].copy()
    rows_after = len(out)
    null_after = {c: int(out[c].isna().sum()) for c in EXPECTED_COLUMNS}
    out = out.sort_values(["icao24", "time"], kind="mergesort").reset_index(drop=True)
    stats = {
        "rows_in": rows_in,
        "rows_after": rows_after,
        "rows_rejected": rows_in - rows_after,
        "null_before": null_before,
        "null_after": null_after,
    }
    return out, stats


def convert_hour(
    tar_path: Path, out_root: Path, date: str, hour: int, nrows: int | None = None
) -> dict:
    df = read_hour(tar_path, nrows=nrows)
    clean_df, stats = clean(df)
    part_dir = out_root / "states" / f"date={date}" / f"hour={hour:02d}"
    part_dir.mkdir(parents=True, exist_ok=True)
    out_file = part_dir / "part-0.parquet"
    clean_df.to_parquet(out_file, engine="pyarrow", index=False)
    stats.update(
        {
            "hour": hour,
            "date": date,
            "source": str(tar_path),
            "sha256": sha256_file(tar_path),
            "source_bytes": tar_path.stat().st_size,
            "parquet": str(out_file.relative_to(REPO_ROOT)) if out_file.is_relative_to(REPO_ROOT)
            else str(out_file),
            "n_aircraft": int(clean_df["icao24"].nunique()),
            "t_min": int(clean_df["time"].min()) if len(clean_df) else None,
            "t_max": int(clean_df["time"].max()) if len(clean_df) else None,
        }
    )
    log.info("hour %02d: %d -> %d rows, %d aircraft", hour, stats["rows_in"],
             stats["rows_after"], stats["n_aircraft"])
    return stats


def convert_day(
    raw_dir: Path, out_root: Path, date: str, nrows: int | None = None,
    report_dir: Path | None = None,
) -> dict:
    files = find_hour_files(raw_dir)
    if not files:
        raise FileNotFoundError(f"no hourly tar files under {raw_dir}")
    hours = []
    for hour in sorted(files):
        hours.append(convert_hour(files[hour], out_root, date, hour, nrows=nrows))
    manifest = {
        "date": date,
        "raw_dir": str(raw_dir),
        "columns": EXPECTED_COLUMNS,
        "n_hours": len(hours),
        "hours": hours,
    }
    report_dir = report_dir or (REPO_ROOT / "results" / "data_report")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "convert_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    log.info("wrote manifest for %d hours", len(hours))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert OpenSky hourly tars to Parquet.")
    ap.add_argument("--date", default="2019-12-09")
    ap.add_argument("--raw-dir", default=None, help="default: <DATA_DIR>/raw/.<date>")
    ap.add_argument("--out-dir", default=None, help="default: <DATA_DIR>/parquet")
    ap.add_argument("--nrows", type=int, default=None, help="rows per hour (smoke only)")
    args = ap.parse_args()

    data_dir = (REPO_ROOT / get_settings().data_dir).resolve()
    raw_dir = Path(args.raw_dir) if args.raw_dir else data_dir / "raw" / f".{args.date}"
    out_root = Path(args.out_dir) if args.out_dir else data_dir / "parquet"
    convert_day(raw_dir, out_root, args.date, nrows=args.nrows)


if __name__ == "__main__":
    main()
