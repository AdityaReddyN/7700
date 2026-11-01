# Scenario, injector and knowledge-base specification

## 1. Labels (exact strings, used everywhere)

| Label | Meaning | Source of ground truth |
|---|---|---|
| `position_spoofing` | False positions injected: gradual drift, sudden jump, or velocity-position mismatch | Construction |
| `ghost_aircraft` | Fabricated track with no genuine history | Construction |
| `replay_duplicate` | Earlier window copied with a time offset, or a duplicated address at distant positions | Construction |
| `sensor_fault` | Noise, dropouts, stuck values or timestamp jitter on a real track | Construction |
| `benign_anomaly` | Real but harmless: holding pattern or go-around | Rule plus visual check |

Five labels. This replaces the earlier six-label design. The `kinematic_spoofing` class was merged into `position_spoofing`, because velocity mismatch and position mismatch are the same signal seen from two sides. Record this trade-off in the write-up.

## 2. Scenario counts

| Item | Count |
|---|---|
| Labels | 5 |
| Scenarios per label | 10 |
| Total scenarios | 50 |
| Knowledge-base case cards per label | 2 (total 10, from KB scenarios only) |
| Dev scenarios per label | 3 (total 15) |
| Test scenarios per label | 5 (total 25) |

Use the same counts for all labels. Difficulty: about one third of each label's scenarios are easy, medium and hard, across splits. Rounding is allowed; record the actual distribution.

## 3. Scenario record
`scenario_id, label, split, difficulty, icao24, t_start, t_end, params, seed, source_track_ref`

- `scenario_id` format: `S` followed by a 4-digit number. Hidden from the model.
- `split` in {`kb`, `dev`, `test`}. KB scenarios produce case cards. Test scenarios are never read by any code that writes to `data/kb/`.
- `seed` fixed per scenario. Generation is fully deterministic from the global seed in `config/scenarios.yaml`.

## 4. Injectors

All injectors take a real track segment from the cleaned store as a starting point, so the injected data has realistic structure. Each injector returns the modified track and a `params` dictionary that is saved for reproducibility.

### 4.1 `position_spoofing`
Three modes, chosen by seed, with equal shares across the class:
- **drift:** add a growing offset to lat and lon, rate 0.05 to 0.5 km per minute, over a window of 4 to 10 minutes. Reported velocity is left unchanged, so implied speed from positions disagrees with reported speed.
- **jump:** shift positions by a fixed offset of 2 to 50 km starting at one timestamp. Reported velocity unchanged.
- **velocity_offset:** keep positions, scale reported velocity by 0.6 to 1.6 for the window. Implied speed from positions now disagrees with reported speed.

Expected signature: implied speed differs from reported speed, residual grows (drift) or spikes (jump), and the track departs from neighbours where the data allow it.

### 4.2 `ghost_aircraft`
- Create a new `icao24` (not present in the file) and a track that starts at `t_start`, so there is no history before the window.
- Path: straight or gently curved, along a heading and speed taken from a real aircraft in the same hour. Cruise speed 400 to 480 knots equivalent. Duration 5 to 20 minutes.
- Add realistic but small position noise (about 20 to 60 m) so the track is not unnaturally perfect.
- Expected signature: no prior history, very smooth kinematics, and possibly no neighbours behaving like it.

### 4.3 `replay_duplicate`
Two modes, equal shares:
- **window_copy:** copy a window of 2 to 10 minutes from another real aircraft, shift its timestamps by an offset of 10 minutes to 6 hours, and attach it to the target `icao24`. The source window must come from the **same day group** as the scenario (see section 6), so the copy never crosses the dev/kb–test boundary.
- **address_duplicate:** keep the target `icao24`, add a second copy of its track shifted by a few seconds in time and a fixed distance (50 to 300 km) in position, so the same address appears in two places at once.

Expected signature: sequence matches an earlier window, same address at distant positions at the same time, or timestamp regressions.

### 4.4 `sensor_fault`
Apply to a real track, and where possible to nearby tracks that share the same time window, to mimic a shared receiver:
- Gaussian position noise, sigma 50 to 500 m.
- Dropouts: remove 10 to 60% of rows for 30 to 120 seconds.
- Stuck values: repeat the last value of one field for 20 to 60 seconds.
- Timestamp jitter: add 1 to 5 seconds of noise to `time`.

Pick one or two of these per scenario, by seed.

Expected signature: random-looking scatter, gaps, repeated values. Neighbours may show the same faults.

### 4.5 Hard variants
- Drift small enough to stay near thresholds.
- Ghost track with realistic noise.
- Replay with an altitude shift.
- Sensor fault that resembles a spoofing jump.

About one third of each label's scenarios should be hard.

## 5. Benign anomalies (`benign_anomaly`)

Find real examples in the cleaned data by rule, then check each one by eye (plot and inspect) before accepting it.

- **Holding pattern:** cumulative heading change of at least 360 degrees within about 6 minutes, with a small radius (under about 5 nautical miles).
- **Go-around:** descent to a low altitude near an airport, followed by a climb of at least 1,000 ft within about 3 minutes. Airport locations are not available in the data; use a rule based on a low altitude followed by a sharp climb, and check by eye. If this is unreliable, drop go-arounds and use holding patterns only.

Confounders: include at least one benign manoeuvre with a sharp turn that resembles a spoofing jump.

If fewer than 10 benign examples can be found and checked, reduce the benign count and report the actual number. Do not pad with unchecked examples.

Diversions and emergency squawks (7700) are excluded for this version. Coverage gaps are excluded because they are hard to separate from sensor faults.

## 6. Splits and leakage

**Day-based split (D-024).** Splits are assigned by day group, not at random within a day. The available days (confirmed in M2) are divided into two groups: a **dev/kb group** and a **test group**. KB and dev scenarios are drawn only from the dev/kb day group; test scenarios only from the test day group. This keeps any shared receiver conditions, traffic patterns and replay source windows from a test day out of the material the model or KB ever sees. If only one day is usable, fall back to the hour-based split (disjoint hours per split) and record the fallback.

- `split.py` assigns splits, writes `data/scenarios/splits.json`, and asserts:
  - No `test` scenario id, track window, **or replay source window** appears in `data/kb/` or in any dev scenario.
  - No test-day window informs a dev or kb scenario (day-group check; hour-group check in the fallback).
  - No KB card references a test scenario.
  - No prompt template contains a scenario id, label name in a leaking position, or split name. The label names appear only in the hypothesis list that the model is supposed to reason about, and never as the answer.
- `tests/test_leakage.py` fails the build if any of these checks fail.
- Labels are never written into alert objects. The alert object contains `alert_id`, `icao24`, time window, score, top features and a human-readable summary.
- The mapping from `alert_id` to `scenario_id` lives in `data/scenarios/alert_map.json`, read only by the evaluation code.

## 7. Detector interaction
- The detector sees alerts, not labels. It runs on all scenarios, including the injected ones, to produce alerts.
- Report detector recall and false-positive rate on dev and on test, with the number of scenarios used.
- If a scenario is not flagged, it is reported as a missed detection and is not evaluated downstream. The evaluation reports how many were missed.

## 8. Knowledge base

### 8.1 Case cards (`data/kb/cards/<card_id>.md`)
Written from **computed statistics on KB scenarios only**, never from memory or from test scenarios.

Template:
```
id: C001
label: position_spoofing
title: Gradual position drift with consistent reported velocity
signature: implied speed exceeds reported speed by about 40 to 60 kt; residual grows linearly over about 4 minutes; neighbours unaffected
differentiators:
  - vs sensor_fault: smooth, monotonic residual with no dropouts or scatter
  - vs velocity_offset: positions and velocity disagree in the other direction
outcome: drift scenario; maximum position offset about 2 km
synthetic: true
source_split: kb
```

Two cards per label, 10 in total. Mark every card `synthetic: true`.

### 8.2 Reference passages (optional, if time)
- At least 3 passages if included. Each is a paraphrased summary of a public source: an open-access paper on ADS-B security, a regulator or agency advisory on GNSS or ADS-B interference, or OpenSky's documentation on data fields.
- Never copy copyrighted text. Keep summaries short and in the agent's own words.
- Record for each: title, URL or citation, retrieval date, one-line summary.
- If unsure about a source's terms, ask the human and leave it out.

### 8.3 Indexing and retrieval
- One chunk per case card. Reference passages split by section at about 400 to 600 tokens.
- Metadata: label, source type, id.
- Retrieval: BM25 always. Add dense embeddings with reciprocal rank fusion only if M6 is on schedule.
- `retrieve_cases(query, hypothesis, k=4)` returns up to 4 items with their `ref_id`s.
- Report recall@4 on dev: the share of dev scenarios where at least one card with the correct label is in the top 4. Expect this to be high, because there are only 10 cards. Say so when reporting it.
