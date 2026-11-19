# Real full-text mini-evaluation

Six frozen tasks, one independent Agent and baseline execution per task. Separate from the historical abstract-only benchmark; no best-of selection or original 250-task rerun.

|Metric|Agent|Baseline|
|---|---:|---:|
|Passed /6|6|1|
|Accuracy|1.0|0.16666666666666666|
|Non-tool accuracy (all 6 tasks)|1.0|0.16666666666666666|
|Average model calls / task|2.6666666666666665|1.0|
|Average latency (seconds)|7.843684937333333|2.597042201166668|
|P95 latency (seconds)|18.424349833|4.549138791999994|
|Average total tokens / task|5181.666666666667|326.3333333333333|
|Usage coverage|1.0|1.0|

|Task|Agent pass|Baseline pass|
|---|---|---|
|fulltext-01|True|False|
|fulltext-02|True|False|
|fulltext-03|True|False|
|fulltext-04|True|False|
|fulltext-05|True|False|
|fulltext-06|True|True|

Both systems have the same role, question and mode description; only Agent can retrieve actual PDF evidence. Baseline receives no passages. This comparison measures evidence access plus the tool loop, not reasoning under equal evidence. All tasks are rubric/unanswerable, so there is no structural tool-grader penalty in this mini-set. Original judge verdicts and reasons are preserved. A manual spot check found overbroad DDPM constant-rate language in fulltext-05 and an unsourced PSNR formula in fulltext-06 despite passed Grounded checks; these are grading limitations, not corrected scores. Baseline emits pseudo-tool markup as plain text on the five body questions; no actual tool executes.

The two separate offline download/parse robustness cases are not paid task executions and are not included in accuracy. No three-run stability claim is made for this small new evaluation.

Source versions, actual PDF/index hashes and parser details are in manifest.json. Full passages stay local; public traces retain PDF page indices, chunk starts, lengths and text hashes for reconstruction. Raw model answers and numeric experimental facts are not changed. The one response containing long PDF quotations is explicitly withheld in the public export with its original hash; it is not replaced by a fabricated answer.

Cost for ALL new calls, including preflight and judge calibration: 41 requests; 61046 reported tokens; $0.12848880000000001 conservative exposure (peak cache-miss rates ×1.25), not an invoice. See budget-summary.json.
