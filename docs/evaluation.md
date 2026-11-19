# Evaluation protocol

Task JSONL has unique `id`, `type` and `question`. Any positive task count is
supported. Additional required fields depend on type:

- exact: `expected` string or list, optional declared `normalization` containing
  casefold/whitespace. Strict compares the whole answer; contains performs literal
  substring matching. Aliases must be frozen before results are inspected.
- tool: `expected_call` with name, arguments and exact/subset matching mode.
  Only the first actual call counts. JSON objects compare structurally (keys
  unordered; exact serialized scalar types preserved). No call means fail.
- rubric / unanswerable: `reference_answer`, `reference_sources` with actual
  evidence and a nonempty rubric list. All Correct, Grounded, Complete, In policy
  and task-specific checks must be true. Unanswerable also requires explicit
  appropriate uncertainty without fabricated facts/sources/actions.

A source URL alone is not reliable evidence to a judge that cannot browse. Put
short supporting passages or verified reference facts in reference_sources.
Source references and task/score metadata never reach the adapter. The judge
receives candidate text as untrusted data and no system identity. Valid JSON and
explicit Boolean checks are mandatory. Missing/malformed/truncated judgments
fail visibly and remain in denominators. The judge is still fallible; the known
historical t44 false positive demonstrates why spot checks matter.

## Frozen identities and resume

Before execution the evaluator records task contents, config, package code/data
hashes, adapter source hash, declared external artifact hashes, model, output cap
and exact policy. Trusted custom adapters must list additional imported code/data
in config.artifacts; automatic recursive dependency discovery is not claimed.
The family hash excludes system/run labels so compatible repeated runs can be
compared; each output directory separately fixes those labels. Mismatches fail
rather than mix results. Do not edit data or code during a formal batch.

Each execution checkpoint is atomically written before grading. If grading is
interrupted, resume grades the persisted answer, without repeating model calls.
Final records are fsync-appended. A malformed trailing JSONL record requires
inspection; it is not silently skipped. One database lock prevents two processes
from appending to the same run concurrently. Failed completed tasks are not
silently retried as if their first outcomes never happened.

## Metrics

Accuracy = passes / total frozen tasks, including failures and grader errors.
Non-tool accuracy excludes tool tasks in numerator and denominator. Partial runs
report completion counts and use the fixed denominator; no-run groups have null
scores. Average model calls is actual API attempts per task, including retries;
tool-call count is separate. End-to-end latency includes tools/retry backoff,
excludes judge time and is in seconds. P95 is nearest-rank ceil(0.95*n).

Token averages use each task's sum across all model rounds, including resent
context. Missing or retry-uncertain usage is null, never zero; coverage is shown.
Reasoning subtokens are not added again to inclusive totals. Judge latency,
usage, attempts and cache state are kept in grade fields, not model metrics.

`stable` takes explicitly named independent runs. pass@k is fraction with any
pass; pass_all_k is fraction passing every run. For k=3 these are pass@3 and
pass^3; no power of aggregate accuracy is used. Incomplete triples are unknown.
Flip tasks have both true and false statuses. Answer changes alone are not flips.

For compatible runs, concatenate their records and report by group:

```sh
cat runs/repeat1/records.jsonl runs/repeat2/records.jsonl runs/repeat3/records.jsonl > /tmp/repeats.jsonl
pae report --tasks benchmarks/online/tasks.jsonl --records /tmp/repeats.jsonl --stability-runs repeat1 repeat2 repeat3
```

Each run is generated using `pae eval ... --run-id repeat1` (or 2/3) and a distinct
output directory. Every request still shares the same global budget. There is
no requirement to repeat new experiments when the remaining budget is too small.

## Historical benchmark

Use `pae history`, not new model calls. It recomputes all per-run/type metrics,
strict and contains, and three-run stability from the 250 portable records.
Original rubric judgments are intentionally retained. The twelve Agent failures
across main/repeats are the same three exact IDs; main baseline structurally
fails all tool questions. Evidence asymmetry is explicit in README.

## New model test set

Six questions reference versioned NeRF and DDPM body sections, plus two separate
own-fixture robustness cases. Questions and references were frozen before any
new paid model execution. Body facts/pages were checked through browser PDF
extraction; actual local PDF byte hashes were recorded after downloads succeeded.
No binary hash or completed score was invented. scripts/prepare_online.py writes
local, cache-only config with downloaded PDF/index/manifest artifacts; formal
evaluation then rejects missing freeze declarations or network fallback.

Run a minimal paid smoke before a full batch, and inspect actual question,
returned evidence, page citation and grader decision. Real text/tool preflight, full-text smoke and positive/negative judge
calibration passed before the six-question formal experiment. Do not present historical abstract scores as evidence
that online/full-text questions pass. A post-fix run must use a new version and
retain failed earlier attempts instead of selecting only the best trial.
