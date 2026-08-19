.PHONY: setup unit ingest search test-one clean

ifneq ($(wildcard .venv/bin/python),)
  PY := .venv/bin/python
else
  PY := python3
endif

setup:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	cp -n .env.example .env 2>/dev/null || true

unit:
	$(PY) -m pytest tests/ -v

test-one:
	$(PY) -m pytest $(FILE) -v

# Session 2 — chunk sample_policy.txt into Chroma (downloads MiniLM once)
ingest:
	. .venv/bin/activate && pip install -e ".[dev,ingest]"
	$(PY) scripts/ingest_corpus.py

search:
	$(PY) scripts/search_chunks.py "$(Q)"

# Session 3 — grounded answer (uses FakeProvider unless you set a real key)
ask:
	$(PY) scripts/ask.py "$(Q)"

clean:
	rm -rf .pytest_cache chroma_db
