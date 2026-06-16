# Study Guide — Become a Strong AI QA Engineer

This repo is your **practice gym**. Each section is a skill, an exercise, and an interview answer template.

## How to use this lab

1. **Read the code** for one layer (e.g. `eval/test_ragas.py`)
2. **Break something on purpose** (lower `k`, weaken system prompt, add bad chunk)
3. **Watch which test fails** and *why*
4. **Fix it** and write a one-line lesson in your notes
5. **Explain it out loud** in 60 seconds (record yourself)

---

## Module 1: RAG fundamentals (Week 1)

### Exercise 1.1 — Ingest and verify
```bash
# Download PDF to corpus/eu_ai_act.pdf
make ingest
make serve   # RAG tab — ask "What is prohibited under Article 5?"
curl localhost:8000/health   # after make api
```

**Pass criteria:** health shows `corpus_chunks > 0`, answer cites Article 5.

### Exercise 1.2 — Golden dataset literacy
Open `eval/datasets/golden.jsonl`. For each `id`:
- Write *why* the expected answer is correct
- Tag whether it's `must_refuse: true` or false

**Add 3 cases** of your own with new `id`s. Run:
```bash
pytest eval/test_ragas.py -v -m eval -k anthropic
```

### Exercise 1.3 — Threshold tuning
Edit `eval/thresholds.yaml`. Lower `faithfulness` to `0.50`, run gate. Raise it back.

**Interview answer:** "I use absolute floors for catastrophes and baseline regression for drift. Floors are calibrated from historical runs, not guessed."

---

## Module 2: Custom metrics (Week 1–2)

### Exercise 2.1 — Read G-Eval rubrics
Open `eval/test_deepeval.py`. Rewrite the `citation_metric` criteria in your own words.

### Exercise 2.2 — Add a metric
Add `Conciseness` G-Eval: penalize answers > 200 words when expected answer is < 100 words.

**Stretch:** add it to `eval/thresholds.yaml` under `deepeval.conciseness`.

### Exercise 2.3 — Trajectory judge
Run agent tab in Streamlit. Compare a *good* trajectory (lookup_article for Article 5) vs a *bad* one (5× search_ai_act).

**Interview answer:** "I test the path, not just the destination. Correct answer via wrong tools is still a regression."

---

## Module 3: Security & adversarial (Week 2)

### Exercise 3.1 — OWASP mapping
Copy the table from `docs/EVAL_STRATEGY.md`. For each row, run the test and read the failure message.

### Exercise 3.2 — Poisoned retrieval
Read `tests/test_rag_security.py`. Explain why this is LLM08, not LLM01.

**Break the system prompt** (remove rule 4). Run unit test. Fix it.

### Exercise 3.3 — Agent injection
Run:
```bash
pytest eval/agent/test_adversarial.py -v -m adversarial
```

Add one new injection string to `USER_INJECTIONS`. Decide if it should fail `_not_pwned` or step budget.

---

## Module 4: Non-determinism (Week 2)

### Exercise 4.1 — Metamorphic
Run the same paraphrase group 3 times. Note score variance.

**Study question:** Why embedding similarity instead of `assert a == b`?

### Exercise 4.2 — Bias pairs
Add a bias pair where framing *should* change the answer (e.g. "AI in schools" vs "AI in hospitals"). Should it be in the suite? Why not?

---

## Module 5: Observability (Week 2)

### Exercise 5.1 — Langfuse setup
1. Sign up at [cloud.langfuse.com](https://cloud.langfuse.com) (free tier)
2. Set `LANGFUSE_*` in `.env`
3. Run one RAG query and one agent query
4. Find traces: retrieve span → llm_generate span → tool spans

### Exercise 5.2 — Debug drill
Set `k=1` in Streamlit. Ask a question needing multiple articles. Find faithfulness drop in eval. Use Langfuse to show wrong chunks.

**Interview answer:** "Every production AI bug needs a trace: input, retrieval, prompt version, model, output."

---

## Module 6: CI & the gate (Week 3)

### Exercise 6.1 — Gate math
Run `make unit` — includes `tests/test_gate.py`. Read `eval/gate.py`.

Manually edit `eval/reports/current.json` to drop faithfulness by 0.10. Run `make gate`. It should fail.

### Exercise 6.2 — Baseline promotion
After a good `make eval-full`:
```bash
make promote-baseline
git diff eval/reports/baseline.json
```

**Study question:** When should you *not* promote baseline?

### Exercise 6.3 — CI cost
Read `eval/conftest.py` caching. Estimate API calls with vs without cache for 12 agent cases.

---

## Module 7: Mock interviews

Practice these **out loud** with the repo open:

1. "Walk me through how you'd test a RAG system." → pyramid in `EVAL_STRATEGY.md`
2. "How do you handle LLM non-determinism?" → metamorphic, G-Eval, thresholds
3. "How do you test an agent differently from RAG?" → `AGENT_QA.md`
4. "What would you put in a CI gate?" → `eval/gate.py` + floors + regression
5. "Tell me about a time you found a regression." → use Exercise 5.2 as a story

---

## Progress checklist

- [ ] `make unit` green locally
- [ ] Corpus ingested, Streamlit demo works
- [ ] Added 3+ golden RAG cases with `id`
- [ ] Langfuse trace screenshot saved
- [ ] `make eval-full` green once
- [ ] Baseline promoted on main
- [ ] Recorded 5-min "how I test RAG" video
- [ ] Added 1 custom G-Eval metric
- [ ] Explained gate vs floor to someone (or rubber duck)

---

## What "best AI QA engineer" means here

Not memorizing metrics — **building systems that catch failures before users do**:

- Fast feedback (unit tests)
- Realistic evals (golden sets, not toy prompts)
- Security mindset (adversarial + poisoned retrieval)
- Cost-aware CI (caching, tiers)
- Debuggable (traces, structured reports)
- Honest docs (README matches code)

This repo is complete when you can **break it, diagnose it, and explain it** without looking at the code.
