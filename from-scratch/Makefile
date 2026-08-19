.PHONY: setup unit ingest search

ifneq ($(wildcard .venv/bin/python),)
  PY := .venv/bin/python
else ifneq ($(wildcard ../.venv/bin/python),)
  PY := ../.venv/bin/python
else
  PY := python3
endif

setup:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	cp -n .env.example .env 2>/dev/null || true

unit:
	$(PY) -m pytest tests/ -v

ingest:
	. .venv/bin/activate && pip install -e ".[dev,ingest]"
	$(PY) scripts/ingest_corpus.py

search:
	$(PY) scripts/search_chunks.py "$(Q)"
