# Data provenance, local caches and rights

## Fixed abstract corpus

Ten author-attributed arXiv abstract/metadata records are bundled under
data/fixed. Versioned URLs, extraction dates and hashes are in data/manifest.json.
Their scope is unchanged from the historical benchmark: abstract and descriptive
metadata, not full papers. The old technical fingerprint, original-record hash
and export changes are documented in benchmarks/historical/provenance.json.
The historical exported answers, judgments, timing and tokens were checked
against the original records; removing local configuration did not change facts.

The arXiv [API terms](https://info.arxiv.org/help/api/tou.html), checked
2026-11-18, identify descriptive metadata (including abstracts) as CC0 1.0.
Paper authorship remains attributed. A paper's PDF/full-text license is separate;
this repository does not distribute downloaded PDFs or long extracted text.
No claim of arXiv endorsement is made.

## Online cache

A metadata query cache records URL, retrieval time and raw-response hash. A paper
manifest records versioned ID, canonical source, download UTC time, byte length,
PDF SHA-256, parser identity/version and index hash/page count. A local PDF and
index are checked against hashes before reuse. Missing/corrupt entries fail
explicitly. New benchmark config lists every PDF, index and manifest for freezing.

Default cache: ~/.cache/paper-agent-eval/arxiv (override --cache for standalone
search/index/retrieve). The recorded full-text benchmark uses .cache/arxiv. Never switch
cache paths or parallel machines to bypass arXiv's aggregate rate limit. The
client's cache-local lock prevents concurrent requests within that shared cache.
The official API user manual and terms are the source for Atom fields, endpoint
and the single-connection, at-least-three-second request policy.

## Parser limits

Portable extraction uses pypdf in a subprocess with a timeout, page cap and
resource caps on supported POSIX systems. macOS can use its PDFKit fallback.
PDFKit is OS-supplied, not shipped here. Parser identity and local page boundaries
are saved. Citations mean file page indices. Printed page numbers may differ.
Neither backend guarantees formula, table or multicolumn reading order. Textless,
encrypted and corrupt PDFs are errors, not invented full-text answers. There is
no OCR or image understanding. Large uncompressed content can still stress a
parser; subprocess limits and size caps reduce, not eliminate, that risk.

## Versioned full-text reference set

NeRF 2003.08934v2 and DDPM 2006.11239v2 were inspected through browser PDF text
extraction. The small test set uses short factual paraphrases and section/page
locations. Both versioned PDFs were subsequently downloaded through the real client and
parsed with pypdf 6.21.4. Actual binary/index hashes, parser version, page count
and download time are recorded in benchmarks/online/manifest.json. Neither
PDF nor its extracted index is published. DiT's browser PDF request
exceeded the browser's size cap, so no full-text test relies on it.

Rebuild on a network-enabled machine with `python scripts/prepare_online.py`.
This fetches the specified versions, records actual hashes and freezes a local
config. The downloaded material remains private and Git-ignored. No parser mock
or own-PDF fixture is represented as an actual arXiv download.

To reproduce the recorded extraction version, install `pypdf==6.21.4` before
running prepare_online.py. Fresh download timestamps change cache-manifest
hashes; do not combine fresh runs with the existing recorded experiment.
