# Roadmap

Today is the start of the build. Day numbering below is relative. The hard deadline is 4 November 2026, 21:00 ET for submission. Aim to submit a day early. Each day ends with a commit and a progress log entry.

## 1. Human-only tasks (the agent cannot do these)

- [x] G1: organizers confirmed Llama is eligible. Reply saved in `docs/permissions/G1-llama.md`.
- [x] G2: OpenSky permission reply received and saved in `docs/permissions/G2-opensky.md`. Follow any stated conditions.
- [~] G3: one day (2019-12-09) of 24 hourly OpenSky files uploaded as `.csv.tar` (partial, D-029). Confirm coverage and the hour-based split in M2.
- [ ] Choose the problem statement (Push the Frontier or Build for Your World).
- [ ] Approve Streamlit (D-008) and the licence (default MIT).
- [ ] Create the public GitHub repository and share the link.
- [ ] Apply for partner credits (Baseten, Modal) if still pursuing them; set a spend limit on any account you use.
- [ ] Claim the Meta Model API credit individually (form deadline 4 November, 21:00 ET), if pursued.
- [ ] Tell the agent your daily time budget.
- [ ] Record the demo video and the fallback take; upload and check the link.
- [ ] Submit on the portal; save the confirmation.

## 2. Day plan (agent work, with human checkpoints)

**Day 1: setup, model gate, data**
- M0 complete: repo, environment, Makefile, `.gitignore`, docs folder, `make test` runs.
- M1 started: `llama3.1:8b` smoke test already has speed numbers. Add the tool-call and structured-output tests on 20 dev prompts each, once the dev prompts exist. Create dev prompts from the scenario builder once M3 is done, or use 20 hand-written neutral prompts in the meantime.
- M2 started: convert the existing CSV to Parquet; write the data report.
- Checkpoint: G1 is answered (yes); primary is local `llama3.1:8b`. No Glimmer, no hosted calls (D-028).

**Day 2: scenarios and detector**
- M3 complete: injectors for the four fault classes, benign finder, splits, leakage test. Labels: 50 scenarios.
- M4 started: rule-based flagger. Alerts for dev and test.
- Checkpoint: detector recall and false-positive rate saved.

**Day 3: tools and first investigation**
- M5 complete: five tools, ToolLog, unit tests.
- M6 partly: case cards (10) written from KB scenarios. Retrieval with BM25.
- M7 started: LLM wrapper, triage, one subagent, verifier.
- Checkpoint (hard stop for the detector): if the rule-based flagger is not giving sane alert rates, keep it as is and stop tuning. Do not start Isolation Forest.

**Day 4: agents end to end**
- M7 complete: subagent loop, adjudicator, orchestrator. Config A and config D each produce one verified `IncidentReport`.
- Measure per-stage time for one case (checkpoint: the time budget in AGENTS.md section 7).
- Decide the test run size and whether to cut subagent calls to 3.

**Day 5: evaluation and app**
- M8: run config A and config D on the test set, overnight if needed (`--resume`). Summarise with one command.
- Start M9: Streamlit Investigate view from the mockup, with the replayed trace.
- Spot-check sheet generated.

**Day 6: app, fallback video, README**
- M9 complete: Report and Benchmark views; live run on a short case; replay labelled correctly.
- Record the fallback video.
- M10 started: README (data report, architecture, results from `results/`, limitations).

**Day 7: video, submission**
- Record the three-minute video. Upload. Check the link logged out.
- Finish the README. Check every number against `results/`.
- Submit with the portal confirmation saved. Target: complete by the evening of 3 November, leaving a day as margin.

## 3. Cut order if time runs short
Cut in this order, and log each cut in DECISIONS.md:
1. Isolation Forest (already optional).
2. Reference passages (case cards only).
3. Glimmer or hosted comparison.
4. Spot-check beyond 10 items.
5. Config A reduced to 10 cases if needed (report it).
6. Test set reduced from 25 to 15 cases (per label: 3), reported as such.
7. Live run in the app (keep replay only, and say so in the video).

Do not cut: the verifier, the evidence/inference split, the verified-only report, the leakage test, the data report, or the honest limitations.

## 4. Blocking items and what happens if unanswered
- G1 resolved: local `llama3.1:8b` is primary (D-023). No Glimmer fallback and no hosted calls (D-028).
- G2 resolved: permission received; follow its conditions. Raw data is still never committed; publish statistics and at most a small sample as the reply allows.
- G3 partial (one day, D-029): replay offsets are within the 24-hour day; the split uses the hour-based fallback. Say so in the README.
- Credits: not needed — inference is local only (D-028). No hosted spend.
