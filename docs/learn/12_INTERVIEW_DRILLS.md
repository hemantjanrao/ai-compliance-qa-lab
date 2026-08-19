# 12 — Interview Drills

Work these **out loud, timed**. Reading them silently produces recognition, not recall. Record yourself on at least three.

---

## 1. The 90-second repo pitch

Practice until it's automatic. Structure: what it is → what's technically interesting → what it proves.

> "It's a production-shaped RAG and agent application over the EU AI Act, built as a laboratory for AI QA practice.
>
> The application layer does hybrid retrieval — BM25 plus dense vectors, merged with reciprocal rank fusion, then reranked with a cross-encoder — and a ReAct agent with four tools over the same corpus.
>
> The interesting half is the eval stack. Five layers: fast unit tests with no API keys, adversarial suites mapped to the OWASP LLM Top 10, RAGAS across eight retrieval and generation metrics, custom G-Eval rubrics for domain-specific properties like citation correctness, and agent trajectory evaluation — because for an agent the path matters as much as the answer.
>
> All of it produces a JSON artifact that a separate gate compares against a committed baseline, checking absolute floors, regression tolerance, latency, and a security ratchet. That gate runs in tiered CI: free unit tests on every PR, cheap adversarial and budget checks after that, and the expensive full suite on manual dispatch.
>
> The thing I'd point at is that the gate itself is unit-tested — it's a pure function over two JSON files, so we can verify our quality gate in milliseconds without spending a cent."

**Drill:** deliver it in 90 seconds. Then in 30. Then in one sentence.

---

## 2. The 5-minute architecture walkthrough

Draw this while talking. Don't recite — narrate the flow.

```
Question
  → guards (LLM05: length/empty)
  → query expansion (rules, no LLM call)
  → article filter extraction
  → dense search (Chroma) × N queries  ─┐
  → BM25 sparse search × N queries     ─┤→ RRF fusion → top 2k
                                         │
  → cross-encoder rerank → top k
  → context assembly with [Source:] tags
  → grounding prompt (4 rules incl. injection defense)
  → LLM (Anthropic | OpenAI via ABC)
  → RAGResult{answer, chunks, tokens, model, provider, retrieval_mode}

Everything traced to Langfuse: chain → retriever → generation
```

Then the eval side:

```
pytest suites → ReportCollector → current.json
                                      ↓
baseline.json + thresholds.yaml → gate.py → exit 0/1 + gate-summary.md
                                      ↓
                        CI: unit → eval-fast → (manual) eval-full
```

**Talking points to hit:**
- Why hybrid (exact identifiers vs semantic)
- Why rerank last (cost is O(candidates))
- Why `answer_with_chunks` is a separate function (testability seam)
- Why measure and gate are separate (pure function, testable, re-runnable free)
- Why CI is tiered (cost)

---

## 3. Rapid-fire question bank

Answer each in 60–90 seconds. ✅ = you can do it cold.

### Retrieval

☐ Why hybrid search instead of just a better embedding model?
☐ What is RRF and why not min-max normalize the scores instead?
☐ Why is `k=60` in RRF, and what happens if you set it to 1?
☐ Bi-encoder vs cross-encoder — why don't you rerank the whole corpus?
☐ How did you pick chunk size? How would you prove it's right?
☐ Your embedding model has a 256-token limit and your chunks are ~500 tokens. What's the consequence?
☐ How do you handle a query about "Article 6" specifically?
☐ What happens if the BM25 index file is missing?

### RAG quality

☐ Explain faithfulness vs answer_relevancy. When do they diverge?
☐ Explain context_precision vs context_recall. Which one does the reranker improve?
☐ Faithfulness dropped 10 points. Walk me through the investigation.
☐ What are the failure modes of LLM-as-judge?
☐ How do you evaluate without ground-truth answers?
☐ What is metamorphic testing and why is it underused?
☐ What's in your golden dataset and how did it grow?

### Security

☐ Direct vs indirect prompt injection — which is worse and why?
☐ How do you test for poisoned retrieval without poisoning your index?
☐ Which OWASP LLM risks does your suite cover? Which don't you cover?
☐ Your adversarial oracle is a keyword list. What's wrong with that?
☐ How do you stop the model from following instructions inside retrieved text?
☐ What's denial-of-wallet and how do you bound it?

### Agent

☐ How is testing an agent different from testing RAG?
☐ Multiple tool sequences can be correct. How do you assert on that?
☐ How do you detect an infinite loop in a trajectory?
☐ What agent-specific attacks have no RAG equivalent?
☐ What logic belongs in the model vs in a tool?
☐ How would your testing change if a tool could send email?

### Eval infrastructure

☐ Why separate measurement from gating?
☐ Why both absolute floors AND regression checks?
☐ Where do your thresholds come from?
☐ How do you control LLM eval cost in CI?
☐ You cache agent trajectories. What does that cost you in fidelity?
☐ What happens when a metric goes missing from the report?
☐ How do you decide when to promote the baseline?
☐ How do you keep a non-deterministic test suite from being flaky?

### Python

☐ ABC vs Protocol — when each?
☐ Why `@wraps`? What breaks without it?
☐ Explain `@contextmanager` — what happens when the body raises?
☐ Why `field(default_factory=list)` instead of `= []`?
☐ You patch `app.rag.get_provider`, not `app.providers.get_provider`. Why?
☐ What does `indirect=True` do in `parametrize`?
☐ `@lru_cache` on a method — what's the risk?
☐ Threads or processes for parallelizing LLM calls? Why?
☐ Why `time.perf_counter()` over `time.time()`?
☐ Why is `math.isnan` needed instead of `== nan`?

---

## 4. Whiteboard prompts

Practice drawing these. 10 minutes each, out loud.

**W1.** Design an eval pipeline for a customer-support RAG bot shipping weekly. What do you measure, what gates the release, and what does CI cost?

**W2.** A user reports the bot gave a confidently wrong answer. Trace your investigation from report to fixed-and-protected.

**W3.** Design the test strategy for an agent that can issue refunds. What's different from a read-only agent?

**W4.** Your team wants to swap the embedding model. Design the migration and the evidence you'd need to approve it.

**W5.** Draw the retrieval funnel and annotate every number (`k`, multiplier, RRF `k`, rerank input size). Justify each.

**W6.** Design a golden dataset for a new domain. How many cases, what fields, how do you source them, how do you know it's enough?

**W7.** Your gate has been red for two weeks and the team wants to disable it. What do you do?

**W8.** Sketch a threshold-calibration procedure from scratch for a metric you've never measured.

---

## 5. STAR stories

Fill these in with your own work on this repo. Write them out; don't improvise them live.

### S1 — "Tell me about a quality problem you found"

- **Situation:** _(e.g. the local embedding model truncates chunks at 256 tokens while chunks are ~500)_
- **Task:** determine impact on retrieval quality
- **Action:** measured cosine similarity of full chunk vs first 200 words; re-ran RAGAS at multiple chunk sizes
- **Result:** _(your numbers)_ — and the change you'd recommend

### S2 — "Tell me about a time you prevented a regression"

- **Situation:** prompt change proposed
- **Task:** determine it was safe
- **Action:** promptfoo v1 vs v2 across both providers and the full golden set; gate on pass rate
- **Result:** measured, not guessed

### S3 — "Tell me about balancing cost and coverage"

- **Situation:** full eval suite costs $1.50–2.50 per run
- **Task:** keep signal, cut spend
- **Action:** three CI tiers; `EVAL_PROVIDERS=anthropic`; local embeddings; trajectory caching keyed on dataset hash
- **Result:** PRs gated for ~$0–0.30; full suite on demand. **Tradeoff acknowledged:** regressions only visible to the full suite are found late

### S4 — "Tell me about something you'd do differently"

Pick one and own it:
- Cache key doesn't include model version → a model bump reuses stale trajectories
- Missing metrics are warnings, not failures → you can believe you're gated when you aren't
- `--promote` doesn't verify the gate passed
- Token pricing hardcoded in `test_budget.py`
- `test_deepeval.py` asserts inside the loop, so a failing metric never gets recorded
- Bias tests conflate "demographic framing changed the answer" with "legally relevant context changed the answer"

**Having a real, specific, self-identified weakness is worth more than a polished feature list.**

---

## 6. Self-assessment scorecard

Rate 1–5. Anything ≤3 is your next study block.

| Area | Can explain | Can implement | Can extend | Can critique |
|---|---|---|---|---|
| Packaging, config, provider abstraction | ☐ | ☐ | ☐ | ☐ |
| Chunking + embeddings | ☐ | ☐ | ☐ | ☐ |
| BM25 | ☐ | ☐ | ☐ | ☐ |
| RRF | ☐ | ☐ | ☐ | ☐ |
| Cross-encoder reranking | ☐ | ☐ | ☐ | ☐ |
| Grounding prompt design | ☐ | ☐ | ☐ | ☐ |
| Prompt injection (direct + indirect) | ☐ | ☐ | ☐ | ☐ |
| OWASP LLM Top 10 mapping | ☐ | ☐ | ☐ | ☐ |
| ReAct loop mechanics | ☐ | ☐ | ☐ | ☐ |
| Tool schema design | ☐ | ☐ | ☐ | ☐ |
| Trajectory evaluation | ☐ | ☐ | ☐ | ☐ |
| Langfuse tracing + debugging workflow | ☐ | ☐ | ☐ | ☐ |
| ReportCollector / artifact design | ☐ | ☐ | ☐ | ☐ |
| pytest hooks + fixtures + parametrize | ☐ | ☐ | ☐ | ☐ |
| Golden dataset design | ☐ | ☐ | ☐ | ☐ |
| RAGAS (all 8 metrics) | ☐ | ☐ | ☐ | ☐ |
| G-Eval rubric writing | ☐ | ☐ | ☐ | ☐ |
| Metamorphic + bias testing | ☐ | ☐ | ☐ | ☐ |
| Latency/cost budgets | ☐ | ☐ | ☐ | ☐ |
| promptfoo | ☐ | ☐ | ☐ | ☐ |
| Gate logic (5 check classes) | ☐ | ☐ | ☐ | ☐ |
| Threshold calibration | ☐ | ☐ | ☐ | ☐ |
| Tiered CI + cost control | ☐ | ☐ | ☐ | ☐ |
| Python: decorators + context managers | ☐ | ☐ | ☐ | ☐ |
| Python: typing (Literal/Protocol/ParamSpec) | ☐ | ☐ | ☐ | ☐ |
| Python: dataclasses | ☐ | ☐ | ☐ | ☐ |
| Python: mocking | ☐ | ☐ | ☐ | ☐ |
| Python: concurrency + GIL | ☐ | ☐ | ☐ | ☐ |

---

## 7. Questions to ask them

Good questions signal seniority as much as good answers.

- "How do you currently decide whether an LLM change is safe to ship? Is there a gate, or is it judgment?"
- "What does your golden dataset look like, and who maintains it?"
- "Do you track cost per query as a quality metric?"
- "How do you handle non-determinism in your test suite — do you have flaky-test suppression, or property-based assertions?"
- "Do you evaluate agent trajectories, or only final outputs?"
- "What's your observability stack for LLM calls, and who looks at it?"
- "How often does your judge model change, and how do you know it hasn't drifted?"
- "What's the most surprising production failure you've had with an LLM feature?"

---

## 8. Traps and how to handle them

| Trap | Weak answer | Strong answer |
|---|---|---|
| "Isn't LLM-as-judge unreliable?" | "It works well enough" | "Yes — self-preference, position bias, and drift. We pin the model and temperature, scope the fields each rubric sees, and layer deterministic checks underneath. The honest next step is calibrating the judge against human labels on a sample." |
| "Your bias test seems naive" | defend it | "It is limited. Embedding invariance conflates 'demographic framing changed the answer' with 'legally relevant context changed the answer' — and for the age-in-hiring pair, a difference may be *correct*. A better design separates strictly-irrelevant attributes and asks a judge whether a difference is justified." |
| "10 samples isn't a p95" | "it's an approximation" | "Correct — `int(10*0.95)-1` is index 8, so it's closer to p90. It's a smoke-level budget check for gross regressions. A real latency SLO needs hundreds of samples from a load harness." |
| "How do you know your thresholds are right?" | "we tuned them" | "You measure run-to-run variance across ~5 identical runs, then set the drop tolerance above the noise floor and the absolute floor below current mean but above the acceptable minimum. Thresholds set without measuring variance produce either a flaky gate or a useless one." |
| "This is a toy project" | get defensive | "It's a lab, deliberately. The corpus is public and the scale is small. What transfers is the structure — tiered CI, artifact-based gating, golden datasets as contracts, trajectory evaluation. At 100× scale I'd change the sparse index, the reranker serving, and blue/green indexing, and I can tell you exactly why for each." |

---

## 9. Daily 20-minute drill

Do this every day of the 7-day plan:

1. **Pick one file.** Explain it out loud in 2 minutes without looking.
2. **Pick one question** from §3. Answer in 90 seconds, timed.
3. **Pick one weakness** from §5 S4. State it and the fix in 60 seconds.
4. **Draw one diagram** from §2 from memory.

Four items, 20 minutes. The compounding is the point.
