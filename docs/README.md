# Docs index

Read in this order before coding. Each file says who owns it.

| # | File | What it covers | Owner |
|---|---|---|---|
| 1 | `../AGENTS.md` | Operating rules, gates, stack, milestones, done criteria | Human |
| 2 | `PROJECT_CONTEXT.md` | Problem, users, hackathon rules, judging, scope, glossary | Human |
| 3 | `DATA_SPEC.md` | OpenSky schema, cleaning, Parquet layout, data report | Agent |
| 4 | `SCENARIO_SPEC.md` | Five labels, injectors, benign rules, splits, KB cards, leakage | Agent |
| 5 | `ARCHITECTURE.md` | Components, pipeline, tools, schemas, LLM wrapper, config | Agent |
| 6 | `PROMPT_SPECS.md` | Prompts and the hypothesis cheat sheet | Agent |
| 7 | `EVALUATION_PROTOCOL.md` | Configs, metrics, verifier definition, statistics, outputs | Agent |
| 8 | `UI_SPEC.md` | Streamlit app: views, interactions, replay vs live | Agent |
| 9 | `API_NOTES.md` | Measured facts on this laptop, Ollama and hosted-API checklist | Agent |
| 10 | `DEMO_AND_SUBMISSION.md` | Three-minute video script, README outline, submission checklist | Both |
| 11 | `ROADMAP.md` | Day plan, human-only tasks, blocking items | Both |
| 12 | `DECISIONS.md` | Decision log, including superseded entries | Agent |
| 13 | `PROGRESS_LOG.md` | Dated milestone entries | Agent |
| 14 | `EXPERIMENT_REGISTRY.md` | One row per evaluation run | Agent |

Rules for all docs: keep them short and current. If code and docs disagree, fix whichever is wrong in the same commit and log it in `DECISIONS.md`.
