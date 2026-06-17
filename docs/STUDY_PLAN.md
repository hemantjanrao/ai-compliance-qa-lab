# 4-Week Study Plan

> **7-day fast track:** see [`ONBOARDING_7_DAYS.md`](ONBOARDING_7_DAYS.md) and [`DAY_02_RAGAS.md`](DAY_02_RAGAS.md) for the condensed onboarding path.

Hours/day target: **2.5 weekday, 4 weekend**. Total ~85 hours.

---

## Week 1 (June 16–22) — RAG Foundations

> **Start here:** [`docs/STUDY_GUIDE.md`](STUDY_GUIDE.md) — exercises for every module.

- [ ] **Tue Jun 16** — `make setup && make ingest && make unit`. Streamlit RAG tab works. Read `docs/EVAL_STRATEGY.md`.
- [ ] **Wed Jun 17** — Theory: tokens, temperature, embeddings, attention intuition. Write `docs/foundations.md` notes.
- [ ] **Thu Jun 18** — RAGAS deep dive. Get `test_ragas.py` green on both providers. Tune thresholds.
- [ ] **Fri Jun 19** — DeepEval G-Eval. Add 2 more custom metrics beyond Citation + Refusal (e.g., Conciseness, Article-Number-Hallucination).
- [ ] **Sat Jun 20** — Expand golden dataset to 30 Q&A. Add `negative` cases (out-of-scope, ambiguous). Version with git tags.
- [ ] **Sun Jun 21** — Push to GitHub. Set up GitHub Actions secrets. Get CI green. Screenshot for portfolio.
- [ ] **Mon Jun 22** — Interview drill: record yourself answering "How would you test a RAG system?" in 5 minutes. Review the recording.

---

## Week 2 (June 23–26) — Adversarial + Observability

- [ ] **Tue Jun 23** — Run `test_adversarial.py`. Fix any failures. Memorize OWASP LLM Top 10.
- [ ] **Wed Jun 24** — Langfuse: set `LANGFUSE_*` in `.env`, run RAG + agent, screenshot trace. See `app/observability.py`.
- [ ] **Wed Jun 25** — Metamorphic + bias tests. Calibrate `eval/thresholds.yaml`. Run `make gate`.
- [ ] **Thu Jun 26** — Read `docs/EVAL_STRATEGY.md` + `docs/AGENT_QA.md`. Mock interview drill.

---

## Travel Period (June 27 – Aug 3) — Theory Only

30-45 min/day. No coding.

- [ ] ISTQB CT-AI syllabus — Chapters 1-10. Make flashcards.
- [ ] OWASP LLM Top 10 — memorize all 10 with one example each.
- [ ] EU AI Act risk tiers — unacceptable / high / limited / minimal.
- [ ] DeepLearning.AI: "Building and Evaluating Advanced RAG" (~2h).
- [ ] DeepLearning.AI: "Red Teaming LLM Applications" (~1.5h).
- [ ] DeepLearning.AI: "AI Agents in LangGraph" (~2h).
- [ ] 1 LeetCode/day to keep coding warm.

---

## Week 3 (Aug 4–10) — Agent Lab

- [ ] **Tue Aug 4** — Scaffold `agent-qa-lab` repo (LangGraph). 3 mock tools: calendar, email-search, weather.
- [ ] **Wed Aug 5** — Test agent failure modes — tool hallucination, loops, plan errors.
- [ ] **Thu Aug 6** — Agent eval: tool selection accuracy, trajectory eval, end-state eval. DeepEval agent metrics.
- [ ] **Fri Aug 7** — promptfoo regression suite on RAG app prompt v1 vs v2.
- [ ] **Sat Aug 8** — Playwright E2E on RAG Streamlit UI with semantic assertions.
- [ ] **Sun Aug 9** — Both repos: clean READMEs, architecture docs, recorded demo videos (5 min each).

---

## Week 4 (Aug 11–17) — Red Team + Interview Mode

- [ ] **Tue Aug 11** — Install garak, run scan against RAG app. Document findings.
- [ ] **Wed Aug 12** — Bias deep-dive: BBQ-style queries. Counterfactual fairness report.
- [ ] **Thu Aug 13** — Guardrails layer: input filter (PII regex + injection classifier), output filter (PII + toxicity).
- [ ] **Fri Aug 14** — Cost + latency dashboard. p50/p95/p99 written up.
- [ ] **Sat Aug 15** — Mock interview 1: 60-min technical deep-dive (use ChatGPT/Claude as interviewer with hard prompt).
- [ ] **Sun Aug 16** — Mock interview 2: system design "QA strategy for an LLM customer support agent". Whiteboard photo.
- [ ] **Mon Aug 17** — Gap review. Update CV with 2 portfolio repos. Refresh LinkedIn.

---

## Daily ritual

- 1.5h skill block (code + concept)
- 30min reading (papers, blogs, syllabus)
- 30min applied (LeetCode or job-app outreach)
- Friday: weekly retro — what shipped, what slipped, adjust next week
