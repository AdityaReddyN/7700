# 7700 — AI incident analyst for ADS-B anomalies

*Named for aviation's universal emergency squawk code — the transponder setting a crew uses when something is wrong in the sky.*

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

