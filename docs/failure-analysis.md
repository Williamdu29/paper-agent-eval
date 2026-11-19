# A reproducible historical failure and a judge limitation

Task t01 asked: “What is the full title of the DUSt3R paper in the catalogue?”
The required title was “DUSt3R: Geometric 3D Vision Made Easy.” In main Agent and
all three independent Agent repeats, the actual final answer was `2312.14132`.
Every trace has one model call, no tool call and no infrastructure error. The
shared catalogue explicitly separated that ID from the correct title, so the
first observable deviation was selecting the wrong field for the final answer.
Retrieval was unnecessary to answer this metadata question. The saved final
assistant message matches the recorded/scored answer; no routing or persistence
defect was found in the original audit. The original outgoing HTTP body was not
independently archived. Field confusion or distraction by tool descriptions is
only a hypothesis, not observed internal reasoning. Both strict and contains
fail this response; extra text is not the reason for failure.

The same stable-failure set includes t03 (expected first submission year 2022;
main/repeats respond 2019/2012/2019/2019) and t16 (expected family CNF/CNFs;
all respond FM, the method alias, with no read of the available abstract).
Changing wrong text without changing pass/fail is not a stability flip.

Separately, baseline t44 claims that NeRF's abstract does not state a camera-pose
requirement. The source supplied to the judge explicitly says “a set of images
with known camera poses.” The judge nevertheless passes Correct and Grounded.
This is a confirmed evidence-reading/criterion-application false positive, not
lack of reference evidence. The input protocol checked source support rather
than citation appearance, but the model did not reliably follow it. Baseline t38
also contains an unsupported extra claim about general source distributions,
and Agent t44 has a completeness concern about an explicit task distinction.
The bounded spot check does not establish an overall judge-error rate.

Original judgments remain in historical results under both exact policies.
Version 0.2.0 strengthens the judge instruction, but has not rerun those model
outputs or silently replaced their scores. All answers, source/tool traces,
judge reasons and numeric facts needed to inspect these failures are retained
in benchmarks/historical/records.jsonl and tasks.jsonl.

## New full-text failures and limitations

In fulltext-01, baseline is asked for NeRF batch size and sampling counts with
PDF pages. It instead says it will search and emits pseudo-tool markup. Its
actual tool trace is empty, because baseline has no tools. The first observable
deviation is producing a tool-intent string instead of an evidence-grounded
answer. This is consistent with the baseline's lack of evidence/access, not
proof of worse reasoning under equal evidence; the judge correctly fails it.

Agent fulltext-02 initially requests an unversioned ID in a cache-only formal
run. The tools return explicit version/cache errors; it searches the frozen
cache, recovers the versioned ID, retrieves page 9 and eventually passes. This
observable argument/recovery trace explains extra model calls without inventing
internal reasoning or hiding the intermediate failures.

The new LLM-judge 6/6 Agent score is not a human claim of flawless grounding.
In fulltext-05, the candidate says "The DDPM learning rate is not decayed over
the course of training"; the retrieved section reports resolution-specific
settings but does not prove a universal absence of decay. fulltext-06 adds an
unsourced PSNR formula despite making the correct refusal. Both pass Grounded.
The original verdicts are preserved, with these evidence-boundary limitations
explicitly disclosed. A response with long verbatim PDF quotes is withheld in
the public export with its original hash, while its unchanged raw answer stays
in local logs. Numeric metrics, scores, usage and timing are unchanged.
