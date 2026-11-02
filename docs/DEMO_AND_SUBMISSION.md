# Demo and submission

## 1. Video (three minutes maximum; the guide requires three minutes)

Target length 2:50. Record one fallback take first, in case the live run fails.

| Time | On screen | What is said |
|---|---|---|
| 0:00 to 0:20 | Title card, then the alert list filling | Operators get more alerts than they can investigate. Detection is the easy part; explanation is the bottleneck. |
| 0:20 to 0:40 | One alert selected; the track with the time scrubber; the feature that flagged it | This track was flagged by an Isolation Forest detector (rule-based fallback). The question is: what caused it? |
| 0:40 to 1:30 | Hypotheses ranked; three debate panels, each with evidence for and against; one live run on a short case (or the replay if the live run is slow) | Each hypothesis gets its own agent. Each agent must find evidence for and against. Every claim cites a tool result. |
| 1:30 to 2:00 | Verification table: verified rows, one excluded row with its reason | Before the report, every cited value is checked against the logged tool output. An unverified claim is removed, not hidden. |
| 2:00 to 2:30 | Verdict, confidence, labelled inference, what would change its mind | The report separates what the data shows from what the model infers. |
| 2:30 to 2:50 | Benchmark view: n = 25, top-1 accuracy with interval, support rate, median time, one-laptop note | Results are from 25 test cases on a laptop. Here is what it got right, what it got wrong, and what I'd fix next. |

Narration rules:
- State the scope and the sample size in the video itself.
- Say "replay" when showing a saved run. Say "live" only for the live run.
- Name the Meta models used and what for: Llama (`llama3.1:8b`) as the primary model, Muse Glimmer only if the optional D-025 comparison is run, and any hosted Muse calls.
- Do not claim generalisation to other domains as a result. It is a pitch statement only.

Video checklist:
- [ ] Readable resolution; clean desktop; no API keys, file paths with personal data, or browser tabs showing secrets.
- [ ] Narration clear; subtitles if possible.
- [ ] Shows: the problem, the investigation, the verified report, the measured results.
- [ ] States the Meta tools used.
- [ ] Under three minutes.
- [ ] Uploaded and link checked from a logged-out browser.

## 2. README outline (public repository)

1. Title, one-line summary, problem statement chosen (Push the Frontier or Build for Your World).
2. Demo link, video link, one screenshot.
3. What it does and who it is for. One paragraph each.
4. Architecture diagram (from ARCHITECTURE.md section 1), with the local and hosted paths marked.
5. How Meta's models are used: which model, which backend, which stage, and why. Include the eligibility basis (guide list, or the organizers' written answer).
6. Data: source (OpenSky), files used, time coverage, the data report summary, licence and attribution text, and the permission status (gate G2).
7. Setup: hardware used, Ollama install, model pull commands, `make setup`, `make run-case`, `make app`.
8. Evaluation: setup, configs, n, metrics table, confusion matrix, error analysis, limitations. All numbers from `results/`, with the run id.
9. Limitations: small test set; synthetic injections; one hour of traffic (or however much is used); CPU-only inference; verifier checks values, not claim wording; the spot-check disagreement rate.
10. What was built during the hackathon, listed explicitly, with the commit range.
11. Licence and third-party components (models, libraries, data).
12. Team and track (solo, Indie Developer).

## 3. Submission checklist
- [ ] Track: Indie Developer. Solo.
- [ ] Problem statement named in the form and README.
- [ ] Public repository, licence file, no secrets, no raw data, no model weights.
- [ ] Git history shows the build during the event window.
- [ ] README complete. Every number traces to `results/`.
- [ ] Video uploaded, under three minutes, link checked logged out.
- [ ] Organizers' written answers (Llama eligibility, OpenSky use) saved in `docs/` and referenced in the README.
- [ ] Credits claimed individually by 4 November, 21:00 ET (if pursued). Spend limit set.
- [ ] Submitted on the portal before 4 November, 21:00 ET, with a saved confirmation. Aim for a day earlier.

## 4. Likely judge questions (prepare answers, check each against results)
- Why not a single agent? Answer with the config A vs D numbers from `results/`, and the sample size.
- How do you know the evidence is real? The verifier checks refs and values. Then the spot-check disagreement rate.
- Why five classes? Each class is a distinct signal, and `kinematic_spoofing` was merged because it overlapped with position spoofing. Say so.
- Does it generalise? Tools and schemas are domain-specific. The pattern (detector, hypothesis agents, verifier, adjudicator) would carry over. State what would change.
- What are the limits? Synthetic injections, one data source, small test set, CPU-only inference, slow per investigation, claim wording not machine-checked.
- Why local models? Data stays on the machine. Limits on speed are measured and reported.
- What did you use from Meta's tooling, and what did each give? List models and the stages they ran, with any measured effects.
- Is this new work? Show the commit history and the list of what was built during the event.
