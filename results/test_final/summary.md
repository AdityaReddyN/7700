# Evaluation summary (M8)

**n = 10 evaluated of 25 test scenarios, one run per config.** The detector alerted on only these; the rest are missed detections (below), so the A-vs-D comparison covers a biased subset — read every number with that in mind.

## Detector coverage on test

- evaluated (had an alert): **10** of 25
- missed (no alert, pipeline never ran): **15**
- missed by label: {'position_spoofing': 5, 'sensor_fault': 5, 'benign_anomaly': 5}

## Config A (n=10)

- top-1 accuracy: **0%** (0/10); 95% bootstrap CI [0%, 0%]
- top-2 accuracy: 20% (2/10)
- evidence support rate: 10% (2/20 items; 7 partial, 11 failed)
- inconclusive: 30% (3/10)
- tool-call validity: 100% (55 tool turns); structured parse 70% (10 calls)
- latency per investigation: p50 212.52s, max 403.97s (one CPU laptop)

| label | n | precision | recall | f1 |
|---|---|---|---|---|
| position_spoofing | 0 | 0% | n/a | n/a |
| ghost_aircraft | 5 | n/a | 0% | 0% |
| replay_duplicate | 5 | n/a | 0% | 0% |
| sensor_fault | 0 | n/a | n/a | n/a |
| benign_anomaly | 0 | n/a | n/a | n/a |

## Config D (n=10)

- top-1 accuracy: **0%** (0/10); 95% bootstrap CI [0%, 0%]
- top-2 accuracy: 10% (1/10)
- evidence support rate: 77% (43/56 items; 0 partial, 13 failed)
- inconclusive: 0% (0/10)
- tool-call validity: 100% (86 tool turns); structured parse 100% (50 calls)
- latency per investigation: p50 588.145s, max 687.71s (one CPU laptop)

| label | n | precision | recall | f1 |
|---|---|---|---|---|
| position_spoofing | 0 | 0% | n/a | n/a |
| ghost_aircraft | 5 | n/a | 0% | 0% |
| replay_duplicate | 5 | n/a | 0% | 0% |
| sensor_fault | 0 | 0% | n/a | n/a |
| benign_anomaly | 0 | n/a | n/a | n/a |

_Numbers from this run's case records; figures alongside. Small n: treat as directional, not conclusive._

