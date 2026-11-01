# Data specification

## 1. Source
OpenSky Network state vectors, exported as hourly CSV files. Gate G2 (permission) is **resolved**: the reply is saved in `docs/permissions/G2-opensky.md`. Follow any conditions it states for publishing derived data or samples. Processing locally for development is allowed; raw data is still never committed.

## 2. Files available now

Gate G3 is **partial**: the raw data on disk is **one day**, 2019-12-09, as 24 hourly tar archives (see D-029). None has been inspected or converted yet; that happens in M2.

| Path | Time coverage (UTC) | Format | Status |
|---|---|---|---|
| `data/raw/.2019-12-09/HH/states_2019-12-09-HH.csv.tar` (HH = 00…23) | 2019-12-09, 24 one-hour files | tar → gzip → CSV (plus `LICENSE.txt`, `README.txt`) | header verified (2026-11-01); full convert in M2 |

Notes:
- The folder name is hidden (leading dot); the M2 converter must not skip dotfiles. Raw data stays gitignored.
- Each `.csv.tar` is a **tar** containing a gzipped CSV (`states_...csv.gz`, ~133 MB compressed) and OpenSky's `LICENSE.txt` and `README.txt`. Conversion untars, then gunzips, then reads the CSV. The bundled licence text backs the attribution note (G2).
- **Header verified 2026-11-01:** the 16 columns match section 3 exactly. Booleans are `True`/`False`, `callsign` is space-padded, `squawk` is a zero-padded string, `time` is int seconds.
- **Measured 2026-11-01 (M2, full day → `results/data_report/`):** 24 hours, 00:00:00–23:59:50 UTC; 54,142,793 rows, 0 rejected (icao24/time never null); 44,879 aircraft, median 726 snapshots/aircraft; null rate after cleaning lat/lon 11.4%, velocity/heading 13.0%, geoaltitude 18.9%, baroaltitude 7.5%, callsign 9.0%, squawk 9.3%; flag share onground 7.6%, alert 2.1%, spi 1.4%. These differ from the 2017 sample below, as expected.

Earlier reference (a different sample, `states_2017-06-05-01.csv`: ~1.44M rows, 9,620 aircraft, ~30 s cadence; ~31% null lat/lon) is kept only as a rough expectation and is **not** assumed to hold for 2019-12-09.

**Split note (D-024 / D-029):** with only one day available, the by-day split falls back to the **hour-based** split (disjoint hours per split). M2 confirms the usable hours and records the split.

## 3. Schema

| Column | Type | Meaning | Notes |
|---|---|---|---|
| `time` | int (Unix seconds) | Snapshot time | Partition key |
| `icao24` | string | Aircraft address | Lowercase hex |
| `lat`, `lon` | float | Position in degrees | Nullable |
| `velocity` | float | Ground speed, m/s | Nullable |
| `heading` | float | Track angle, degrees | Nullable |
| `vertrate` | float | Vertical rate, m/s | Nullable |
| `callsign` | string | Flight callsign | Nullable; may be padded |
| `onground` | bool | On ground | Never null |
| `alert` | bool | OpenSky alert flag | **Do not use as a feature** |
| `spi` | bool | Special position identification flag | **Do not use as a feature** |
| `squawk` | string | Transponder code | Nullable |
| `baroaltitude`, `geoaltitude` | float | Altitude, metres | Nullable |
| `lastposupdate`, `lastcontact` | float | Seconds since last position or any message | `lastposupdate` nullable |

Check the actual header on arrival and record any difference in `DATA_SPEC.md` and DECISIONS.md.

## 4. Cleaning rules (in order)
1. Parse types. Reject rows where `icao24` or `time` is missing.
2. Keep rows where `lat`, `lon`, `velocity`, `heading` and `vertrate` are all non-null for features that need them. Other rows stay in the Parquet store but are excluded from the detector.
3. Do not impute or interpolate positions in the raw store. Imputation, if any, happens inside an explicitly named feature with a documented rule.
4. Never modify raw files. Write derived data to `data/parquet/` only.
5. Record the row count after each rule in the data report.

## 5. Parquet layout
- `data/parquet/states/date=YYYY-MM-DD/hour=HH/part-0.parquet`
- Sorted by `icao24`, then `time`, within each file.
- Typed columns as in section 3, with explicit dtypes.

## 6. Data report (`make report`)
Writes `results/data_report/report.md` and `summary.json`, containing:
- Files used, with checksums (SHA-256) and file sizes.
- Time coverage per file and total.
- Row counts before and after cleaning rules.
- Null rate per column, before and after cleaning.
- Aircraft count per hour, and median snapshots per aircraft.
- Share of rows with each flag (`onground`, `alert`, `spi`), reported but not used as features.
- A note on data licence and attribution text, including any conditions from the OpenSky permission reply (`docs/permissions/G2-opensky.md`, gate G2).

This report is a deliverable. It goes in the README.

## 7. Using the data for scenarios
- Injected scenarios are built from **real tracks in the cleaned store**, then modified. Raw data is never edited.
- Scenario tracks are written to `data/scenarios/tracks.parquet`, keyed by `scenario_id`.
- Tools see a **scenario-aware view**: the scenario track plus surrounding real traffic from the same time window. Tools never see the label or the scenario id.
- Benign anomalies are found in real data by rule (see SCENARIO_SPEC.md) and checked by eye.

## 8. Limits to state in the README
- Coverage is one day (2019-12-09), up to 24 one-hour windows, not representative of all traffic. Report the exact coverage used, from `results/data_report/`.
- Position data are reported by aircraft and not verified against any authority.
- Synthetic injections are not real attacks. Results measure detection and explanation on injected faults, not on real-world attacks.
