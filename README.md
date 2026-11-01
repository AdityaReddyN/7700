# AeroMuse — AI incident analyst for ADS-B anomalies

> **Status: work in progress (M0 scaffolding).** The public README with results,
> figures and limitations is written in M10. Every number published here must
> come from a file in `results/`.

An AI incident analyst for ADS-B aircraft-tracking anomaly alerts, built for the
Meta Global AI Developer Hackathon 2026 (Indie Developer track, solo). A
rule-based detector flags suspicious tracks; a triage step ranks five
hypotheses; a subagent per hypothesis investigates with five read-only tools and
retrieval; a pure-Python verifier checks every cited piece of evidence; an
adjudicator writes an incident report that separates verified evidence from
inference.

See `AGENTS.md` for the operating rules and `docs/README.md` for the reading
order.

## Quick start

```bash
make setup   # create .venv and install pinned dependencies
make test    # run the test suite
```

On Windows, install GNU make (`choco install make`) or use `mingw32-make`.

## Assumptions in force (gates not yet resolved)

- **G1 (model eligibility):** primary model is a config value in
  `config/models.yaml`. Default is `llama3.1:8b` via Ollama; falls back to a
  local 2-bit model if Llama is ruled ineligible.
- **G2 (OpenSky permission):** no OpenSky-derived data is published until
  permission is confirmed. Raw data is never committed.
- **D-008 (UI) and D-020 (problem statement):** awaiting human decision; see
  `docs/DECISIONS.md`.

Licence: pending human decision (default MIT). Data: OpenSky Network, cited per
their terms once G2 is resolved.
