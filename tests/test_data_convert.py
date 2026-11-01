"""M2 convert + report on a synthetic tar->gz->csv fixture (hermetic, no raw data)."""

import gzip
import io
import tarfile
from pathlib import Path

import pandas as pd

from data.convert import EXPECTED_COLUMNS, convert_day
from data.report import write_report

_HEADER = ",".join(EXPECTED_COLUMNS)
# time,icao24,lat,lon,velocity,heading,vertrate,callsign,onground,alert,spi,
# squawk,baroaltitude,geoaltitude,lastposupdate,lastcontact
_ROWS = [
    "1575849600,abc123,43.6,-78.8,220.6,72.4,13.0,WJA252  ,False,False,False,0532,5974.0,5897.8,1575849598.8,1575849600.0",
    "1575849600,abc123,43.7,-78.7,221.0,70.0,12.0,WJA252  ,False,True,False,0532,6000.0,5900.0,1575849599.0,1575849600.0",
    "1575849601,def456,40.0,-75.0,,,,,True,False,False,,,,,1575849601.0",  # feature-nulls: KEPT
    "1575849602,,41.0,-75.0,200.0,90.0,0.0,TST001  ,False,False,False,1200,100.0,90.0,1.0,2.0",  # no icao24: DROP
    ",ghi789,42.0,-76.0,200.0,90.0,0.0,TST002  ,False,False,False,1200,100.0,90.0,1.0,2.0",  # no time: DROP
]


def _make_fixture(raw_dir: Path, date: str = "2019-12-09", hour: int = 0) -> None:
    csv_bytes = (_HEADER + "\n" + "\n".join(_ROWS) + "\n").encode("utf-8")
    gz_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buf, mode="wb") as g:
        g.write(csv_bytes)
    gz_bytes = gz_buf.getvalue()
    hour_dir = raw_dir / f".{date}" / f"{hour:02d}"
    hour_dir.mkdir(parents=True, exist_ok=True)
    tar_path = hour_dir / f"states_{date}-{hour:02d}.csv.tar"
    with tarfile.open(tar_path, "w") as tf:
        for name, payload in [
            (f"states_{date}-{hour:02d}.csv.gz", gz_bytes),
            ("LICENSE.txt", b"OpenSky terms"),
            ("README.txt", b"OpenSky sample"),
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))


def test_convert_and_report(tmp_path: Path):
    raw = tmp_path / "raw"
    out = tmp_path / "parquet"
    report_dir = tmp_path / "report"
    _make_fixture(raw)

    manifest = convert_day(raw / ".2019-12-09", out, "2019-12-09", report_dir=report_dir)

    # Partition path and parquet exist.
    part = out / "states" / "date=2019-12-09" / "hour=00" / "part-0.parquet"
    assert part.exists()

    df = pd.read_parquet(part)
    # 5 rows in, 2 dropped (missing icao24 / missing time) -> 3 kept.
    assert len(df) == 3
    assert df["time"].notna().all()
    assert df["icao24"].notna().all()
    # Sorted by icao24, then time.
    assert list(df["icao24"]) == sorted(df["icao24"])
    # Types.
    assert str(df["time"].dtype) == "Int64"
    assert df["lat"].dtype == "float64"
    assert str(df["onground"].dtype) == "boolean"
    # Feature-null row is kept with nulls intact.
    assert df["velocity"].isna().sum() == 1
    # Callsign stripped.
    assert "WJA252" in set(df["callsign"].dropna())

    hour0 = manifest["hours"][0]
    assert hour0["rows_in"] == 5
    assert hour0["rows_after"] == 3
    assert hour0["rows_rejected"] == 2
    assert hour0["n_aircraft"] == 2
    assert len(hour0["sha256"]) == 64

    # Report assembles from manifest + parquet.
    glob = str(out / "states" / "**" / "*.parquet").replace("\\", "/")
    summary = write_report(report_dir / "convert_manifest.json", glob, report_dir)
    assert summary["rows"]["after_cleaning"] == 3
    assert summary["rows"]["before_cleaning"] == 5
    assert summary["aircraft_total"] == 2
    assert summary["flag_share"]["alert"] is not None
    assert (report_dir / "report.md").exists()
    assert (report_dir / "summary.json").exists()
    assert "OpenSky" in (report_dir / "report.md").read_text(encoding="utf-8")
