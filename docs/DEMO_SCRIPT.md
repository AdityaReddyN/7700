# AeroMuse — 3-minute demo video script

**Target: ≤ 3:00.** Narration is ~430 words (~145 wpm, relaxed). Built to the rubric:
Impact 30% · Use of Meta AI 25% · Demo 25% · Technical Depth 20%.

Production notes
- Record the Streamlit app (`make app`) at a clean window size; cursor visible.
- Use the **replayed** cases (labelled 🔁) so the pipeline runs instantly — do **not**
  wait for a live CPU run on camera. If you want one live moment, pre-record a config-A
  run separately and speed it up; keep the LIVE label on screen.
- Headline run for numbers: `test_final` (pick it in the sidebar "Eval run" for Benchmark).
- Keep claims to what's on screen. Do not say the detector "catches spoofing" — it doesn't
  (that's the honesty beat). Every number shown is read from `results/`.

---

### 0:00–0:20 — Hook + the stakes  *(Impact)*
**[ON SCREEN: Overview page — hero + stat cards.]**

> "Every aircraft overhead broadcasts its position on an open radio protocol called ADS-B.
> It is completely **unauthenticated** — anyone with a cheap radio can forge a position, a
> speed, or an identity. Spoofing, ghost aircraft, replay attacks: these are real threats
> to aviation and drones, and security teams get far more alerts than any human can read.
> Meet **AeroMuse** — an AI incident analyst for exactly these alerts."

### 0:20–0:42 — What it is + Meta/Llama  *(Use of Meta AI)*
**[ON SCREEN: point to the sidebar Llama badges and the "How it works" architecture strip.]**

> "AeroMuse runs a **team of Llama models entirely on a laptop** — Llama 3.2 3B triages,
> Llama 3.1 8B investigates — with native tool-calling and structured output, through
> Ollama. **No cloud, zero inference cost, data never leaves the machine** — which matters
> for sensitive airspace and defense data. Five stages: detect, triage, investigate,
> **verify**, and adjudicate."

### 0:42–1:15 — See the threat  *(Demo + Impact)*
**[ON SCREEN: Anomaly gallery → "position spoofing" → an example scenario. Let the two plots draw.]**

> "First, the threat itself. Every anomaly is injected into **real OpenSky flight data**.
> Here's GPS position spoofing: the black line is the speed the aircraft *reports* — but the
> **red line is the speed its own positions imply**. Watch them diverge. That gap is the
> spoof, made visible. And notice this chip — it reads the **detector's real recall straight
> from our results file**. On this class it's honest about what we do and don't catch yet."

### 1:15–2:05 — The investigation + the verifier  *(Technical Depth + Use of Meta AI)*
**[ON SCREEN: Investigate view → pick a flagged case → expand the stage steps.]**

> "When a track is flagged, AeroMuse investigates. **Triage** ranks five hypotheses.
> A **subagent per hypothesis** gathers evidence using five read-only, deterministic tools —
> the model never writes code or SQL, and the tools have no network access. Then the part
> I'm proudest of: a **pure-Python verifier re-checks every number the model cites against
> the logged tool output**. If a claim doesn't match, it's dropped — not shown. So the final
> report separates **verified evidence** from inference, and a confident guess with no backing
> becomes an honest *inconclusive*."

### 2:05–2:35 — Proof it works  *(Impact + Technical Depth)*
**[ON SCREEN: Benchmark view, Eval run = test_final.]**

> "Does the verifier actually help? Here's the measured benchmark — every number traced to a
> file. The single-agent baseline grounds just **10%** of its evidence. The full pipeline with
> the verifier grounds **77%**. That's the jump from a chatbot that sounds sure to a report an
> analyst can **trust**. We also report where it's weak — small-model accuracy on the hardest
> classes — because honest measurement is the point."

### 2:35–3:00 — Close  *(Impact)*
**[ON SCREEN: back to Overview hero.]**

> "AeroMuse turns one unauthenticated radio signal into a ranked, **evidence-verified**
> incident report — private, local, and free to run, on open Llama models. It's a blueprint
> for AI triage you can actually deploy where the data can't leave the building. That's
> AeroMuse. Thanks for watching."

---

## Timing cheat-sheet
| Beat | End | Screen |
|---|---|---|
| Hook / stakes | 0:20 | Overview hero |
| Meta/Llama + architecture | 0:42 | Sidebar badges + strip |
| Spoofing visual | 1:15 | Anomaly gallery |
| Pipeline + verifier | 2:05 | Investigate steps |
| Benchmark (10% → 77%) | 2:35 | Benchmark (test_final) |
| Close | 3:00 | Overview hero |

## One-line backups (if a judge asks)
- **"Did it detect the spoof?"** — "The detector reliably flags ghost and replay anomalies
  (100% recall on test); position-spoofing recall is currently 0% — a measured limitation we
  show on screen, with a clear fix path (spoofing-specific detector features)."
- **"Why Llama / local?"** — "Open weights let this run on-prem with zero cloud cost and full
  data control — essential for aviation/defense telemetry."
- **"What's the novel bit?"** — "A verifier that gates an LLM's claims against deterministic
  tool output, turning a small local model into a trustworthy, auditable analyst."

---

## Recording checklist

**Before you hit record**
- Launch: `make app` (or the running instance). Browser at **1280×720** or **1920×1080**, 16:9.
- Close other tabs; hide bookmarks bar; full-screen the browser. Cursor visible.
- Sidebar should already show the **Llama badges** and **Eval run = test_final** (now the default).
- Zoom the page so the hero + stat cards fit one screen (Ctrl/Cmd + "−" once if needed).
- Audio: record narration separately (phone/USB mic) if your screen-recorder's mic is noisy;
  it's easier to re-take audio than video.

**Tools (any one)**
- OBS Studio (free, best control) — scene = browser window capture, 1080p/30, record to MP4.
- Windows: Xbox Game Bar (Win+G) for a quick capture. macOS: Cmd+Shift+5.
- Edit/trim: Clipchamp (Win), iMovie (mac), or DaVinci Resolve (free).

**Click path (matches the script beats)**
1. **Overview** — start here; let the hero + cards + architecture strip sit on screen.
2. **Anomaly gallery** → *position spoofing* → example scenario. Best drift visuals:
   **S0003** or **S0010** (clear, steady speed divergence). Also worth showing **replay_duplicate**
   (S0021/S0027 — obvious repeated path) and **ghost_aircraft** (no identity).
3. **Investigate** — pick any case; expand *Triage*, one *Subagent*, then the open *Adjudication*.
   Point at the verified/failed evidence counts.
4. **Benchmark** — leave Eval run on **test_final**; land on the **10% → 77%** support contrast.
5. Back to **Overview** for the close.

**Pacing**
- ~3:00 total. Rehearse once with a stopwatch; the per-beat end-times are in the cheat-sheet above.
- Don't wait for a live CPU run on camera — use the 🔁 replays. If you want one live shot,
  pre-record a config-A run and speed it up 4–8×, keeping the **LIVE** label visible.
- Record in **sections** (one per beat) and stitch — far easier than one perfect take.

**Honesty guardrails (keep you safe with judges)**
- Don't say the detector "catches" spoofing. The on-screen recall chip tells the truth;
  lean on the **verifier + 10%→77%** story and **local/private/$0** instead.
- If asked about accuracy, use the backup lines above (detector 100% recall on ghost/replay;
  spoofing recall 0% is a measured gap with a known fix).
