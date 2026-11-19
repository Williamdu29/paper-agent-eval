# Observed validation

Verified on 2026-11-18. Offline, live network, model and historical evidence are
separate; fixtures are never counted as real model responses.

## Offline and installed-package checks

- 24 offline tests cover generic/non-paper adapters, model/tool loops, task
  isolation, fixed/online separation, resume and version mismatch, grading,
  usage/latency/stability, shared budget accounting, redaction, URL/ID boundaries,
  cache corruption and PDF/page/chunk behavior.
- The original macOS PDFKit fallback was exercised with an own-authored PDF.
  The portable pypdf path subsequently passed the same tests after installation.
- A wheel was installed into a fresh temporary environment, and tests, the CLI,
  historical recomputation and the non-paper example were run outside the source
  directory. The source does not depend on its former parent or a hidden key.
- All 250 historical exported records were compared against original fields.
  Answers, tool traces, scores, timing and usage facts remain unchanged.
  Original task questions, expected values, rubrics and scoring policies remain
  unchanged; portable source paths are documented in provenance.json.

## Real network and PDF checks

After execution permissions were restored, official arXiv metadata search worked.
NeRF 2003.08934v2 and DDPM 2006.11239v2 were downloaded, hashed and parsed with
pypdf 6.21.4, each with 25 PDF file pages. Actual PDF/index hashes, parser identity
and download time are in benchmarks/online/manifest.json. Page 9 of NeRF and
pages 14–15 of DDPM were inspected against the task reference facts. Public
artifacts do not include PDFs, extracted indexes or long source passages.

## Real model validation

All requests used the single budgeted DeepSeek client and one persistent ledger.
Real text connectivity and an actually executed local function roundtrip passed.
An independent full-text Agent smoke and blind positive/negative judge
calibration also passed before the frozen formal mini-evaluation.

The formal mini-evaluation contains 6 Agent and 6 baseline executions. Agent
receives tools; baseline receives the same role/question/mode description but
no retrieved passages. LLM-judge scores are 6/6 and 1/6. Both pass the refusal
case; baseline's other responses contain pseudo-tool markup or an intention to
search without actual tool execution. No three-run stability measurement is
claimed for this new mini-set, and historical stability is not mixed into it.

Manual spot checks support the required numeric body facts and PDF pages. They
also found that Agent fulltext-05 overstates the absence of any DDPM decay, and
fulltext-06 introduces a PSNR formula without source retrieval. Judge Grounded
still passes them. These are disclosed limitations, not silently corrected
verdicts. The historical baseline t44 false positive remains documented too.

All new requests together: 41 API requests, 52,633 reported prompt tokens,
8,413 reported completion tokens, 61,046 total tokens. Conservative exposure is
$0.1284888 at peak cache-miss prices with a 1.25 safety multiplier, not a provider
invoice. There were no retry or uncertain-usage groups. This includes preflight,
smoke, calibration, formal Agent/baseline and judge. The historical experiment's
cost is excluded. No remaining budget was spent to manufacture a better score.

## Release checks

Candidate files, staged blobs, the built wheel and accessible Git history are
scanned for a known key in memory, credential patterns, private paths and excluded
materials. Secret values are never printed. No original environment file, old
Git history, private cache or original archive is imported. The repository-local
Git author uses the authenticated personal owner's verified noreply identity
when no valid existing identity is configured; global Git settings are unchanged.

The release script verifies personal ownership, avoids existing repositories,
creates a public repository, pushes without force and checks branch/remote SHA.
Post-push verification includes a clean remote clone and offline tests. Actual
workflow status is visible in GitHub Actions; no simulated badge or success
claim substitutes for those checks. CI has read-only repository permissions,
requires no model key, sends no paid requests and downloads no papers.
