# AeroMuse / adsb-analyst — task runner.
# Windows note: install GNU make (e.g. `choco install make`) or use mingw32-make.
# The venv lives in .venv; PY points at its interpreter.

ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python
else
PY := .venv/bin/python
endif

.PHONY: setup data report scenarios alerts kb smoke test run-case eval summarize app lint

# --- M0: environment -------------------------------------------------------
setup:
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests

# --- M2: data (not implemented until M2) -----------------------------------
data:
	$(PY) -m data.convert

report:
	$(PY) -m data.report

# --- M3: scenarios ---------------------------------------------------------
scenarios:
	$(PY) -m scenarios.inject

# --- M4: detector / alerts -------------------------------------------------
alerts:
	$(PY) -m detector.alerts

# --- M6: knowledge base ----------------------------------------------------
kb:
	$(PY) -m kb.build_index

# --- M1: model smoke tests -------------------------------------------------
smoke:
	$(PY) -m agents.llm --smoke

# --- M7: single investigation ----------------------------------------------
run-case:
	$(PY) -m agents.orchestrator

# --- M8: evaluation --------------------------------------------------------
eval:
	$(PY) -m eval.run_eval

summarize:
	$(PY) -m eval.summarize

# --- M9: app ---------------------------------------------------------------
app:
	$(PY) -m streamlit run src/app/streamlit_app.py
