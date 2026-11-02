# Project context

## One-line summary
An AI incident analyst for ADS-B aircraft-tracking anomalies. An Isolation Forest detector (rule-based fallback) flags suspicious tracks. Parallel-in-design (sequential on this laptop) hypothesis agents test competing explanations with tools and retrieval. A verifier checks every cited fact. An adjudicator writes a report that separates evidence from inference.

## The problem
Operators of surveillance and sensor networks receive more anomaly alerts than they can investigate. Deciding whether an alert is spoofing, a sensor fault, a replay, a fabricated aircraft or a harmless manoeuvre is slow and repetitive, and real incidents get lost in the noise. The tool shortens the time from alert to understanding and shows its evidence, so a human can trust or challenge it.

## Who it is for (pitch)
- Airspace and surveillance analysts who monitor ADS-B feeds.
- Infrastructure and security operations teams with sensor networks that rely on position data.
- Researchers studying ADS-B integrity.

The pitch may note that the same pattern (detector, hypothesis agents, verifier, adjudicator) applies to other sensor data such as ships or industrial sensors. This is a pitch claim only. Do not build it.

## Why it can run on a laptop
The model runs locally, so no operator data leaves the machine. This is a real selling point for restricted or air-gapped networks. The demo must prove that it works end to end on a 16 GB laptop, even if slowly.

## Hackathon facts (from the official participant guide)

**Event:** Meta Global AI Developer Hackathon 2026, virtual. Building period 27 October to 4 November 2026.

**Problem statements (choose one):**
- *Build for Your World:* bring Meta's models into your domain, solve a problem you know firsthand.
- *Push the Frontier:* use Meta's models for software, robotics, manufacturing, energy and beyond, give a machine a new capability or unlock a better way to understand and control a physical system.

**Required Meta tools.** The guide lists: Muse Spark series, Muse Wonder, Muse Image, Muse Voice Transcribe, SAM 3.1 (through Meta Model API), Muse Glimmer and Muse Spark Open (open weights), and Muse Code. Llama is not named in that list, but the organizers have **accepted Llama models as eligible** (gate G1 resolved; reply saved in `docs/permissions/`). See gate G1 in AGENTS.md.

**Open-weight use.** The guide says open-weight models may run through partner hosts (Baseten, Modal, Fireworks) and names Muse Glimmer and Muse Spark Open as eligible. Local running is not explicitly addressed in the text the human pasted. Confirm with organizers if it matters for judging.

**Track.** Indie Developer. Solo entry (maximum team size four; this project is solo).

**Rules that matter for this build:**
- Repository must be public.
- Demo must highlight only what was built during the hackathon. Judges must be able to identify original work. Failure to do so can lead to disqualification.
- New work only. Startups may build on existing codebases; indie entries must show what is new.
- No projects that violate legal, ethical or platform policy, or use code, data or assets without rights. This includes OpenSky data (gate G2).
- Avoid the anti-project list: basic RAG applications, simple image analysers, generic chatbots, political or war-related projects, medical advice tools, and similar. This project must lead with the hypothesis testing, verifier and evaluation, not with retrieval.

**Submission.** Through the Cerebral Valley portal, by 4 November 2026, 21:00 ET. Requires: public repository, accessible video link, everyone who worked on the project listed. Three-minute demo video.

**Judging.** Stage 1: pass or fail. The project reasonably fits the theme and reasonably uses Meta's models. Stage 2: scored 0 to 10 on a rubric. Stage 3: top five per track go to live final judging.

The rubric weights noted earlier (Impact 30%, Tooling 25%, Demo 25%, Technical 20%) came from an earlier source and have **not been verified against the official rubric table**. Do not rely on them in the README until verified.

**Credits.** $150 Meta Model API credit, claimed individually by 4 November at 21:00 ET, with a card required. Whether the credit covers open-weight models is unconfirmed. Partner credits (Baseten, Modal, Fireworks) are requests only and not guaranteed. The team's Modal balance is $1.

## Scope

**In scope (must):**
- Data conversion and a data report.
- Isolation Forest detector (rule-based fallback) with measured precision and recall on injected data.
- Five hypothesis classes, with fresh injectors.
- Five read-only tools with `ref_id` and a tool log.
- Triage, subagent loop, verifier, adjudicator, orchestrator.
- Config A (single agent) and config D (full pipeline) on a 25-case test set.
- Streamlit app with replay and one live run.
- README, video, submission.

**In scope (if time):**
- BM25 plus embedding retrieval (BM25 alone is acceptable).
- Three or more paraphrased reference passages with sources.
- Ten-case spot-check of verifier claims.

(The Glimmer comparison and any hosted Muse call are out of scope per D-028: local Llama only.)

**Out of scope:**
- GRU autoencoder, FastAPI and SSE, React UI, Docker.
- Five-way ablation, full 150-case evaluation, speedup claims unless measured.
- Real-time ingestion, authentication, cloud deployment, multi-domain implementation.
- Model training or fine-tuning.
- Any reuse of earlier research code.

## Owner
Aditya. Solo developer with an ML, deep learning and RAG background. Works on one Lenovo Yoga laptop (16 GB, Intel Iris Xe).

## Glossary
- **ADS-B:** Automatic Dependent Surveillance-Broadcast. Aircraft broadcast position and velocity, unauthenticated.
- **icao24:** 24-bit aircraft address, shown in hex.
- **State vector:** one timestamped record of an aircraft's reported state.
- **Squawk:** four-digit transponder code. 7700 means emergency.
- **Spoofing:** injecting false ADS-B messages.
- **Ghost aircraft:** a fabricated track with no genuine source.
- **Replay:** re-broadcasting captured messages at a later time.
- **Kinematic consistency:** whether reported velocity and altitude agree with how the position changes.
- **Coverage gap:** a period where receivers cannot hear an aircraft. Can be benign.
- **Verifier:** pure-Python check that cited evidence exists in the tool log and matches stated values.
- **Leakage:** test-split information reaching the knowledge base, prompts or tools. Forbidden.
- **Ablation:** a run with one design feature removed, to measure its contribution.
- **Inference (in reports):** the model's reasoning. Always labelled separately from evidence.
