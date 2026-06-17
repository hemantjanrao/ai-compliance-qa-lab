.PHONY: setup ingest serve api unit eval eval-fast eval-full gate promote-baseline calibrate clean garak-redteam promptfoo-eval e2e-ui

setup:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	cp -n .env.example .env 2>/dev/null || true

ingest:
	python scripts/ingest_corpus.py

serve:
	streamlit run app/streamlit_ui.py

api:
	uvicorn app.main:app --reload --port 8000

unit:
	. .venv/bin/activate && pytest tests/ -v

eval-fast:
	. .venv/bin/activate && pytest tests/ eval/test_adversarial.py eval/agent/test_adversarial.py eval/test_budget.py -v -m "not slow" --tb=short
	. .venv/bin/activate && python -m eval.gate --markdown eval/reports/gate-summary.md || true

eval:
	. .venv/bin/activate && pytest tests/ eval/ -v -m "not slow" --tb=short
	. .venv/bin/activate && python -m eval.gate --markdown eval/reports/gate-summary.md

eval-full:
	. .venv/bin/activate && pytest tests/ eval/ -v --tb=short
	. .venv/bin/activate && python -m eval.gate --markdown eval/reports/gate-summary.md

gate:
	. .venv/bin/activate && python -m eval.gate --markdown eval/reports/gate-summary.md

promote-baseline:
	. .venv/bin/activate && python -m eval.gate --promote

calibrate:
	@echo "Run eval-full on main, then: make promote-baseline"
	@echo "This stores your last-known-good metrics in eval/reports/baseline.json"

garak-redteam:
	bash scripts/garak_scan.sh

promptfoo-eval:
	npx --yes promptfoo@latest eval -c promptfoo/promptfooconfig.yaml

e2e-ui:
	. .venv/bin/activate && pytest tests/e2e/test_streamlit_ui.py -v -m slow

clean:
	rm -rf .eval_cache .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
