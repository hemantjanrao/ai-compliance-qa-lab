.PHONY: setup ingest serve api unit eval eval-fast eval-full gate promote-baseline calibrate clean garak-redteam promptfoo-eval e2e-ui

# Use .venv when present (local dev); fall back to PATH python (CI after pip install -e).
ifneq ($(wildcard .venv/bin/python),)
  PY := .venv/bin/python
else
  PY := python3
endif

setup:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	cp -n .env.example .env 2>/dev/null || true

ingest:
	$(PY) scripts/ingest_corpus.py

serve:
	streamlit run app/streamlit_ui.py

api:
	uvicorn app.main:app --reload --port 8000

unit:
	$(PY) -m pytest tests/ -v

eval-fast:
	$(PY) -m pytest tests/ eval/test_adversarial.py eval/agent/test_adversarial.py eval/test_budget.py -v -m "not slow" --tb=short
	$(PY) -m eval.gate --markdown eval/reports/gate-summary.md || true

eval:
	$(PY) -m pytest tests/ eval/ -v -m "not slow" --tb=short
	$(PY) -m eval.gate --markdown eval/reports/gate-summary.md

eval-full:
	$(PY) -m pytest tests/ eval/ -v --tb=short
	$(PY) -m eval.gate --markdown eval/reports/gate-summary.md

gate:
	$(PY) -m eval.gate --markdown eval/reports/gate-summary.md

promote-baseline:
	$(PY) -m eval.gate --promote

calibrate:
	@echo "Run eval-full on main, then: make promote-baseline"
	@echo "This stores your last-known-good metrics in eval/reports/baseline.json"

garak-redteam:
	bash scripts/garak_scan.sh

promptfoo-eval:
	python scripts/generate_promptfoo_tests.py
	npx --yes promptfoo@latest eval -c promptfoo/promptfooconfig.yaml -o promptfoo/output.json

e2e-ui:
	$(PY) -m pytest tests/e2e/test_streamlit_ui.py -v -m slow

clean:
	rm -rf .eval_cache .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
