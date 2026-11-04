"""7700 — M9 Streamlit app: Anomaly Gallery, Investigate, Report, Benchmark.

White background, black text, red accents. Reads only `results/<run>/` (eval
runs), `runs/` (live traces) and `data/scenarios/tracks.parquet` (for the track
pictures). Every metric is read from a committed file (AGENTS non-negotiable #3).
Saved traces are labelled REPLAY; the one optional live run is labelled LIVE
(AGENTS §9). Detection status chips are read from results/detector — a
position-spoofing track is shown to illustrate the anomaly, and the chip states
the detector's real recall on that class (0% on test — a documented limitation),
so nothing here overclaims. Streamlit (D-008) is the assumed UI.

Run with: `make app`
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from app import loader, plots

st.set_page_config(page_title="7700 — ADS-B incident analyst", layout="wide")

_PCT = lambda x: "n/a" if x is None else f"{100 * x:.0f}%"  # noqa: E731

_CSS = """
<style>
  .stApp { background:#FFFFFF; color:#111111; }
  h1,h2,h3,h4 { color:#111111 !important; }
  h1 { border-bottom:4px solid #D7263D; padding-bottom:.2em; }
  h2 { border-left:6px solid #D7263D; padding-left:.5rem; }
  .chip { display:inline-block; padding:2px 10px; border-radius:12px;
          font-size:0.8rem; font-weight:600; margin-right:6px; }
  .chip-red { background:#FDE7EA; color:#D7263D; border:1px solid #D7263D; }
  .chip-grey{ background:#F0F0F2; color:#444; border:1px solid #CFCFD4; }
  [data-testid="stMetricValue"] { color:#111111; }
  .redword { color:#D7263D; font-weight:700; }
  .hero { border:1px solid #ECECEF; border-left:8px solid #D7263D; border-radius:10px;
          padding:1.1rem 1.3rem; background:#FCFCFD; margin-bottom:1rem; }
  .hero h1 { border:none; margin:0 0 .3rem 0; font-size:2.1rem; }
  .hero .tag { color:#D7263D; font-weight:700; letter-spacing:.04em;
               text-transform:uppercase; font-size:.8rem; }
  .cards { display:flex; gap:14px; flex-wrap:wrap; margin:.4rem 0 1rem; }
  .card { flex:1 1 160px; border:1px solid #ECECEF; border-radius:10px; padding:.8rem 1rem;
          background:#FFFFFF; }
  .card .num { color:#D7263D; font-size:1.8rem; font-weight:800; line-height:1.1; }
  .card .lab { color:#444; font-size:.82rem; margin-top:.2rem; }
  .arch { display:flex; align-items:stretch; gap:0; flex-wrap:wrap; margin:.3rem 0 1rem; }
  .step { flex:1 1 0; min-width:120px; border:1px solid #E6E6EA; border-radius:8px;
          padding:.6rem .7rem; background:#FFFFFF; position:relative; }
  .step b { color:#111; font-size:.92rem; } .step small { color:#666; }
  .step.red { border-color:#D7263D; background:#FDF2F4; }
  .arrow { align-self:center; color:#D7263D; font-weight:800; padding:0 .35rem; }
</style>
"""


@st.cache_data(show_spinner=False)
def _tracks():
    return loader.scenario_tracks()


def _chip(text: str, red: bool = False) -> str:
    return f'<span class="chip {"chip-red" if red else "chip-grey"}">{text}</span>'


# --------------------------------------------------------------------------- #
# Overview — impact-first landing
# --------------------------------------------------------------------------- #
_ARCH = [
    ("Detector", "Isolation Forest flags suspect tracks", False),
    ("Triage", "Llama 3.2 3B ranks 5 hypotheses", False),
    ("Subagents", "Llama 3.1 8B + 5 read-only tools", False),
    ("Verifier", "pure Python — gates every claim", True),
    ("Adjudicator", "verified-only incident report", False),
]


def _stat_cards(headline: Path | None) -> str:
    support = "—"
    if headline:
        m = loader.load_metrics(headline).get("D", {})
        es = m.get("evidence_support", {})
        if es.get("support_rate") is not None:
            support = f"{es['support_rate'] * 100:.0f}%"
    cards = [
        (support, "evidence verified in the report (config D)"),
        ("$0", "cloud cost — 100% local inference"),
        ("5", "read-only, deterministic tools"),
        ("2", "Llama models, on a 16 GB laptop"),
    ]
    inner = "".join(f'<div class="card"><div class="num">{n}</div>'
                    f'<div class="lab">{lbl}</div></div>' for n, lbl in cards)
    return f'<div class="cards">{inner}</div>'


def view_overview(headline: Path | None) -> None:
    models = loader.models_used()
    badge = (f"{models.get('primary', 'Llama 3.1 8B')} + {models.get('triage', 'Llama 3.2 3B')} "
             f"· local via {models.get('backend', 'ollama').title()}")
    st.markdown(
        f'<div class="hero"><div class="tag">AI incident analyst · ADS-B airspace security</div>'
        f'<h1>7700</h1>'
        f'<div style="color:#666;font-size:.92rem;margin:-.3rem 0 .5rem;">aviation\'s universal '
        f'<b>emergency squawk</b> — the code a crew sets when something is wrong in the sky</div>'
        f'<p style="font-size:1.05rem;margin:.2rem 0 .5rem;">ADS-B aircraft signals are '
        f'<b>unauthenticated</b> — anyone can forge a position, speed or identity. 7700 '
        f'triages spoofing and anomaly alerts and writes an incident report where every '
        f'number is <span class="redword">verified against the data</span>, running '
        f'<b>entirely on a laptop</b> — no cloud, private by default.</p>'
        f'{_chip(badge, red=True)}{_chip("no third-party inference")}</div>',
        unsafe_allow_html=True)

    st.markdown(_stat_cards(headline), unsafe_allow_html=True)

    st.subheader("How it works")
    steps = []
    for i, (name, desc, red) in enumerate(_ARCH):
        steps.append(f'<div class="step {"red" if red else ""}"><b>{name}</b><br>'
                     f'<small>{desc}</small></div>')
        if i < len(_ARCH) - 1:
            steps.append('<div class="arrow">→</div>')
    st.markdown(f'<div class="arch">{"".join(steps)}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Why it matters.** GPS/position spoofing, ghost aircraft and replay "
                    "attacks are real threats to aviation and drones. Security teams face more "
                    "alerts than they can read. 7700 turns one alert into a ranked, "
                    "evidence-backed story an analyst can trust in minutes.")
    with c2:
        st.markdown("**Honest by construction.** A pure-Python verifier re-checks every cited "
                    "value, so unsupported claims are dropped, not shown. We measure and report "
                    "what fails — including a small-model accuracy ceiling on the hardest "
                    "classes (see Benchmark).")
    st.caption("Use the sidebar: Anomaly gallery → Investigate → Report → Benchmark. "
               "Every number shown is read from a file in results/.")


# --------------------------------------------------------------------------- #
# Anomaly Gallery — the picture-first view
# --------------------------------------------------------------------------- #
def _recall_pct(det: dict | None, label: str) -> float | None:
    if not det:
        return None
    pc = det.get("test", {}).get("per_class", {}).get(label)
    return pc.get("recall") if pc else None


def view_gallery() -> None:
    st.header("Anomaly gallery — what the system is built to catch")
    st.write("Each anomaly type is injected into **real OpenSky tracks**. "
             "The <span class='redword'>red</span> series is always the anomalous "
             "signal, so the drift or jump is visible at a glance.", unsafe_allow_html=True)

    by_label = loader.scenarios_by_label()
    if not by_label:
        st.warning("No scenarios found under data/scenarios/.")
        return
    det = loader.detector_metrics()
    order = ["position_spoofing", "replay_duplicate", "ghost_aircraft",
             "sensor_fault", "benign_anomaly"]
    labels = [x for x in order if x in by_label]

    label = st.selectbox("Anomaly type", labels, index=0,
                         format_func=lambda x: x.replace("_", " "))
    st.markdown(loader.LABEL_BLURB.get(label, ""))
    rec = _recall_pct(det, label)
    chips = _chip(f"{len(by_label[label])} scenarios")
    if rec is not None:
        chips += _chip(f"detector recall (test): {_PCT(rec)}", red=(rec < 0.5))
    st.markdown(chips, unsafe_allow_html=True)
    if rec is not None and rec < 0.5:
        st.caption("⚠️ The detector currently misses most of this class (see Benchmark). "
                   "The track below illustrates the anomaly; it is not a claim that the "
                   "pipeline flagged it.")

    scen = st.selectbox("Example scenario", by_label[label],
                        format_func=lambda s: f"{s['scenario_id']} · {s.get('difficulty', '')}")
    df = loader.track_by_scenario(_tracks(), scen["scenario_id"])
    params = scen.get("params", {})
    if params:
        st.caption(f"injection parameters: {params}")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(plots.track_map(df), use_container_width=True)
    with c2:
        st.plotly_chart(plots.speed_drift(df), use_container_width=True)
    c3, c4 = st.columns([1, 1])
    with c3:
        st.plotly_chart(plots.residual(df), use_container_width=True)
    with c4:
        st.plotly_chart(plots.altitude(df), use_container_width=True)


# --------------------------------------------------------------------------- #
# Benchmark view
# --------------------------------------------------------------------------- #
def _caveat(missed: dict | None) -> str:
    if not missed:
        return "Small test set (25 scenarios). Read numbers as directional."
    n_ev, n_test = missed.get("n_evaluated"), missed.get("n_test")
    by = missed.get("missed_by_label", {})
    return (f"The detector alerted on **{n_ev} of {n_test}** test scenarios, so the "
            f"A-vs-D comparison covers that biased subset only; **{n_test - n_ev} missed** "
            f"({by}). n is small — directional, not conclusive.")


def view_benchmark(run_dir: Path) -> None:
    st.header("Benchmark — config A vs D")
    missed = loader.load_missed(run_dir)
    st.info(_caveat(missed))
    metrics = loader.load_metrics(run_dir)
    if not metrics:
        st.warning("No metrics.json — run `make summarize` first.")
        return
    configs = sorted(metrics)
    rows = []
    for c in configs:
        m = metrics[c]
        acc, es, lt = m["accuracy"], m["evidence_support"], m["latency"]
        rows.append({
            "config": loader.CONFIG_LABELS.get(c, c),
            "top-1": f"{_PCT(acc['top1'])} ({acc['top1_count']}/{acc['n']})",
            "top-2": f"{_PCT(acc['top2'])} ({acc['top2_count']}/{acc['n']})",
            "evidence support": f"{_PCT(es['support_rate'])} ({es['verified']}/{es['n_items']})",
            "inconclusive": _PCT(m["inconclusive"]["rate"]),
            "parse ok": _PCT(m["llm_quality"]["structured_parse_rate"]),
            "latency p50": "n/a" if lt["p50"] is None else f"{lt['p50']:.0f}s",
        })
    st.subheader("Headline metrics")
    st.table(rows)

    col1, col2 = st.columns(2)
    with col1:
        fig = go.Figure()
        fig.add_bar(name="top-1", x=configs, marker_color="#D7263D",
                    y=[metrics[c]["accuracy"]["top1"] or 0 for c in configs])
        fig.add_bar(name="top-2", x=configs, marker_color="#111111",
                    y=[metrics[c]["accuracy"]["top2"] or 0 for c in configs])
        fig.update_layout(template="plotly_white", title="Accuracy by config",
                          yaxis_range=[0, 1], barmode="group", height=360,
                          paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig2 = go.Figure()
        fig2.add_bar(x=configs, marker_color="#D7263D",
                     y=[metrics[c]["evidence_support"]["support_rate"] or 0 for c in configs])
        fig2.update_layout(template="plotly_white",
                           title="Evidence support rate (verified / cited)",
                           yaxis_range=[0, 1], height=360,
                           paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
        st.plotly_chart(fig2, use_container_width=True)

    if missed:
        st.subheader("Detector coverage on the test split")
        st.write(f"Evaluated (had an alert): **{missed.get('n_evaluated')}** of "
                 f"{missed.get('n_test')}. Missed: **{len(missed.get('missed_scenarios', []))}** "
                 f"— {missed.get('missed_by_label')}.")
    figs = loader.figures(run_dir)
    if figs:
        st.subheader("Figures (from results/)")
        cols = st.columns(2)
        for i, path in enumerate(figs):
            cols[i % 2].image(str(path), caption=path.name, use_container_width=True)


# --------------------------------------------------------------------------- #
# Shared: incident report + track pictures for an alert
# --------------------------------------------------------------------------- #
def _confidence_note(report: dict) -> str | None:
    meta = report.get("meta", {}) or {}
    if meta.get("verdict_overridden"):
        return (f"Verdict adjusted: the model proposed `{meta.get('proposed_verdict')}`, "
                f"which no subagent supported, so the grounded result is shown instead.")
    return None


def _alert_tracks(alert: dict | None) -> None:
    if not alert:
        return
    df = loader.track_window(_tracks(), alert.get("icao24"),
                             alert.get("t_start"), alert.get("t_end"))
    if df.empty:
        st.caption("No track rows found for this alert window.")
        return
    st.subheader("Flight picture")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(plots.track_map(df), use_container_width=True)
    with c2:
        st.plotly_chart(plots.speed_drift(df), use_container_width=True)


def _render_report(report: dict, alert: dict | None, *, replay: bool,
                   show_tracks: bool = True) -> None:
    if replay:
        st.caption("🔁 REPLAY of a saved trace — not a live run.")
    verdict, conf = report.get("verdict", "?"), report.get("confidence")
    c1, c2, c3 = st.columns(3)
    c1.metric("Verdict", verdict)
    c2.metric("Confidence", "n/a" if conf is None else f"{conf:.2f}")
    c3.metric("Excluded (unverified) claims", report.get("excluded_evidence_count", 0))
    note = _confidence_note(report)
    if note:
        st.warning(note)
    if alert:
        st.caption(f"Alert `{alert.get('alert_id')}` — {alert.get('summary')}")
    if show_tracks:
        _alert_tracks(alert)

    st.subheader("Verified evidence (only)")
    table = report.get("evidence_table", [])
    if table:
        st.table([{"claim": e.get("claim"), "source": e.get("source"), "stat": e.get("stat"),
                   "value": e.get("value"), "ref_id": e.get("ref_id")} for e in table])
    else:
        st.write("_No evidence survived verification for this case._")

    st.subheader("Ranked hypotheses")
    for r in report.get("ranked", []):
        st.markdown(f"- **{r.get('hypothesis')}** — {r.get('verdict')} "
                    f"(subagent confidence {r.get('confidence')})")
    st.subheader("Reasoning (inference, not evidence)")
    st.write(report.get("inference") or "_none_")
    if report.get("recommended_action"):
        st.markdown(f"**Recommended action:** {report['recommended_action']}")


def view_report(run_dir: Path) -> None:
    st.header("Report — one incident")
    by_config = loader.load_cases(run_dir)
    if not by_config:
        st.warning("No cases in this run.")
        return
    config = st.selectbox("Config", sorted(by_config, key=lambda c: (c != "D", c)),
                          format_func=lambda c: loader.CONFIG_LABELS.get(c, c))
    case = st.selectbox("Case", by_config[config],
                        format_func=lambda c: f"{c['alert_id']} · verdict: {c['verdict']}")
    trace = loader.load_trace(run_dir, config, case["alert_id"])
    if not trace:
        st.warning("Trace not found.")
        return
    _render_report(trace.get("report", {}), trace.get("alert"), replay=True)


# --------------------------------------------------------------------------- #
# Investigate view
# --------------------------------------------------------------------------- #
def _render_steps(trace: dict) -> None:
    for step in loader.stage_steps(trace):
        secs = step["seconds"]
        head = step["title"] + (f"  ·  {secs:.0f}s" if isinstance(secs, int | float) else "")
        with st.expander(head, expanded=(step["kind"] == "adjudication")):
            body = step["body"]
            if step["kind"] == "triage":
                if body.get("fallback"):
                    st.caption("rule-based fallback priors")
                st.table([{"hypothesis": k["hypothesis"], "prior": k["prior"],
                           "reason": k.get("reason")} for k in body.get("kept", [])])
            elif step["kind"] == "subagent":
                st.markdown(f"verdict **{body['verdict']}** · confidence {body['confidence']} "
                            f"· tool calls {body['tool_calls_used']}")
                v = body.get("verification")
                if v:
                    st.caption(f"verified {v.get('n_verified')}/{v.get('n_total')} "
                               f"(partial {v.get('n_partial')}, failed {v.get('n_failed')})")
                for e in body.get("evidence", []):
                    st.markdown(f"- {e.get('claim')} — `{e.get('stat')}`={e.get('value')} "
                                f"({'verified' if e.get('verified') else 'unverified'})")
                if body.get("inference"):
                    st.write(body["inference"])
            elif step["kind"] == "verification":
                st.table([{"hypothesis": v.get("hypothesis"), "total": v.get("n_total"),
                           "verified": v.get("n_verified"), "partial": v.get("n_partial"),
                           "failed": v.get("n_failed")} for v in body.get("per_hypothesis", [])])
            else:
                _render_report(body, trace.get("alert"), replay=False, show_tracks=False)


def _live_run(config: str, alert_id: str, run_dir: Path) -> None:
    from agents.orchestrator import investigate_sync
    from common.schemas import Alert
    from tools.registry import default_provider, default_retriever

    trace = loader.load_trace(run_dir, config, alert_id)
    if not trace:
        st.error("Could not load the alert.")
        return
    alert = Alert(**trace["alert"])
    with st.spinner(f"Running config {config} live on {alert_id} — minutes on CPU…"):
        incident, live = investigate_sync(alert, config, provider=default_provider(),
                                          retriever=default_retriever())
    st.success(f"LIVE run complete — verdict {incident.verdict} ({incident.confidence:.2f}).")
    _render_report(live.get("report", {}), live.get("alert"), replay=False)


def view_investigate(run_dir: Path) -> None:
    st.header("Investigate — step through the pipeline")
    by_config = loader.load_cases(run_dir)
    if not by_config:
        st.warning("No cases in this run.")
        return
    st.caption("🔁 REPLAY — these steps are read from a saved trace.")
    config = st.selectbox("Config", sorted(by_config, key=lambda c: (c != "D", c)),
                          key="inv_config",
                          format_func=lambda c: loader.CONFIG_LABELS.get(c, c))
    case = st.selectbox("Case", by_config[config], key="inv_case",
                        format_func=lambda c: f"{c['alert_id']} · {c['verdict']}")
    trace = loader.load_trace(run_dir, config, case["alert_id"])
    if trace:
        _alert_tracks(trace.get("alert"))
        _render_steps(trace)
    with st.expander("⚡ Run live on this case (config A, slow on CPU)"):
        st.caption("A real run through Ollama — minutes on this laptop. Labelled LIVE.")
        if st.button("Run live (config A)"):
            _live_run("A", case["alert_id"], run_dir)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.sidebar.markdown("## 7700")
    st.sidebar.caption("AI incident analyst for ADS-B anomaly alerts")
    models = loader.models_used()
    st.sidebar.markdown(
        _chip(f"⚡ {models.get('primary', 'llama3.1:8b')}", red=True)
        + _chip(f"{models.get('triage', 'llama3.2:3b')}"), unsafe_allow_html=True)
    st.sidebar.caption("Meta Llama · 100% local via Ollama · $0 cloud")
    runs = loader.eval_runs()
    view = st.sidebar.radio(
        "View", ["Overview", "Anomaly gallery", "Investigate", "Report", "Benchmark"])
    run_dir = None
    if runs:
        headline = loader.headline_run()
        idx = runs.index(headline) if headline in runs else 0
        run_dir = st.sidebar.selectbox("Eval run", runs, index=idx,
                                       format_func=lambda p: p.name)
    st.sidebar.caption("🔁 replays · ⚡ live. Every number is read from results/.")

    if view == "Overview":
        view_overview(loader.headline_run())
        return
    if view == "Anomaly gallery":
        view_gallery()
        return
    if not run_dir:
        st.title("7700")
        st.warning("No eval runs under results/. Run `make eval` then `make summarize`.")
        return
    if view == "Benchmark":
        view_benchmark(run_dir)
    elif view == "Report":
        view_report(run_dir)
    else:
        view_investigate(run_dir)


main()
