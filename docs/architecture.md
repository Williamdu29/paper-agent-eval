# Architecture and implementation review

The evaluator knows only `Input`, `Result`, task/grading data and a trusted
adapter factory. Paper tools are a reference integration, not a required core
service. A deterministic reverse-string example runs through the same evaluator
without importing a paper module or constructing a provider.

|Feature|Source|Evidence / limit|
|---|---|---|
|Input/Result contract|src/paper_agent_eval/contracts.py|Question and allowed context only; trace/status/usage explicit|
|Generic model/tool loop|agent.py|Bounded model turns and context; locally executed calls; no hidden reasoning persistence|
|Paid request boundary|provider.py|Only code that sends DeepSeek headers; fixed HTTPS endpoint, redirects disabled, explicit retries|
|Durable budget|budget.py|SQLite BEGIN IMMEDIATE reservations, restart tests, uncertain-charge retention|
|Task loading/identity/checkpoints|evaluation.py|Arbitrary nonempty task sets, per-task atomic checkpoint, config/code/data hashes, serialized run lock|
|Graders|grading.py|Exact and structural first-call checks independent of adapter; blind JSON judge with source excerpts|
|Aggregation|metrics.py|Task-set-derived denominators, usage coverage, nearest-rank P95, independent stability states|
|Fixed paper tools|papers.py: Fixed|Ten static filenames; no network fallback; no arbitrary file tool|
|arXiv metadata/PDF download|arxiv.py|Validated IDs/hosts/redirects; shared serialized requests and interval; size/time caps; cache hashes|
|Text extraction/retrieval|retrieval.py, pdfworker.py, pdfkit.swift|Own-PDF extraction plus real NeRF/DDPM PDFs; page-local chunks, BM25-style lexical ranking, bounded evidence|
|Historical export and recomputation|history.py; benchmarks/historical|250 preserved real records; two exact policies; old version fingerprint|
|Developer extension|example.py; examples/reverse.*|Offline non-paper evaluation, resume and changed-config rejection tests|
|Publication scan|scripts/audit_release.py|Candidate files, staged blobs, all commit blobs and credential-bearing remote checks|

## Session and error semantics

Each task obtains a new adapter and tool session. Agent and baseline share role,
question and catalogue; baseline has no tools and one generation. Tool results
are returned as data, including explicit failures. An empty/truncated answer,
turn cap, timeout, provider failure, budget stop or adapter exception cannot be
a passing refusal. Completed failures remain in denominators; missing usage is
null. Tool operations are finite local work or bounded network/parse operations.
Third-party adapters must implement their own timeout/status contract; the core
does not sandbox arbitrary Python or forcefully preempt a custom infinite loop.

## State and trust boundaries

Task answers, types, references and rubrics never enter `Input`. Local adapter
configuration is trusted executable configuration, not model-generated data.
PDFs/abstracts may contain prompt injections; the system role explicitly treats
them as untrusted text. This is mitigation, not proof against every model error.
Models cannot select filesystem paths. PDF parser subprocesses receive no
credential-bearing environment variables; parsers do not execute document code.

Network paper requests have separate headers from the DeepSeek transport.
Downloads are constrained to arXiv hosts, modern paper-ID paths and HTTPS; no
private host, credential URL, file URL, port override or arbitrary redirect.
The local cache is user-owned and is not an adversarial multi-user sandbox.
A shared SQLite gate serializes connections across processes using that cache.
Users must not create additional caches/machines to evade arXiv's aggregate rate
limit; one client is intended per operator.

## Technical version relationship

The historical benchmark fingerprint is retained in provenance.json, with hashes
of the original grader and adapter sources. Portable exports remove local
configuration and make source references relative; answer, score, trace, timing
and usage facts remain unchanged. Version 0.2.0 reorganizes and extends the code,
changes the judge instruction to explicitly check unsupported absence claims,
and adds online/PDF/budget features. It has NOT rerun the original 250 tasks.
Historical scores still use the old judge, including its documented mistakes.
No old repository history or artifacts were imported as development commits.

The separate six-question full-text experiment records its own package-code,
configuration, task and artifact fingerprint in benchmarks/online/experiment.json.
It includes actual PDFs parsed with pypdf 6.21.4; no new code is claimed to have
reproduced the historical responses.
