# Detector report (M4)

Method: **rules** (Isolation Forest is primary; rule-based flagger is the
fallback, D-030). Threshold 50.0000, set by a 5% false-positive budget on normal dev-hour traffic (D-031); the achieved
false-positive rate on the baseline was 52%. The
**test** split was scored once with it. Recall is whatever this operating point
yields — the detector is deliberately simple and favours a believable alert rate
over catching every subtle injection.

Baseline: 3000 real airborne windows from hours
[6, 7, 8, 9, 10, 11] (dev-group hours, disjoint from the test hours — no test
traffic is seen). 12 features per window.

**Small samples.** Each split has only a handful of scenarios per class
(dev: 12 injected + 3 benign;
test: 20 injected + 5 benign). Read
every rate as indicative, not precise.

## Dev

Overall injected recall 58%
(7/12); precision 100%;
benign flag rate 0%.

| class | flagged / total | recall |
|---|---|---|
| position_spoofing | 0 / 3 | 0% (recall) |
| ghost_aircraft | 3 / 3 | 100% (recall) |
| replay_duplicate | 3 / 3 | 100% (recall) |
| sensor_fault | 1 / 3 | 33% (recall) |
| benign_anomaly | 0 / 3 | 0% (flag rate) |

## Test (scored once)

Overall injected recall 75%
(15/20); precision 88%;
benign flag rate 40%.

| class | flagged / total | recall |
|---|---|---|
| position_spoofing | 1 / 5 | 20% (recall) |
| ghost_aircraft | 5 / 5 | 100% (recall) |
| replay_duplicate | 5 / 5 | 100% (recall) |
| sensor_fault | 4 / 5 | 80% (recall) |
| benign_anomaly | 2 / 5 | 40% (flag rate) |

## Alert rate on real traffic

1121 of 2000 uninjected real windows from hours
[20, 21, 22, 23] were flagged: **56%**. This is a false-positive proxy
on unlabelled real traffic, not a measured precision.

Total alerts written for the pipeline: 24 (dev + test flagged windows).

_Generated 2026-11-02T02:44:08+00:00. Every number here traces to
`results/detector/metrics.json`._
