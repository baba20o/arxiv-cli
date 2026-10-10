# Proposal: versioned paper text extraction

Status: design feedback only; the commands below are proposed, not implemented.

## Observed gap

In a five-paper reading trial, all version-pinned PDF downloads succeeded.
Reading methods, results and tables still required a separate
`pdftotext -layout` step. One conversion emitted
`Syntax Warning: Mismatch between font type and embedded font file` while
producing readable text. Successful download and successful extraction therefore
need separate outcomes; a parser warning does not necessarily mean failure.
This small trial did not test scanned PDFs, HTML coverage or extraction accuracy.

Today [the download client](../arxiv/api.py) streams a PDF to disk and returns a
path. [The CLI](../arxiv/cli.py) exposes `download`, `abstract` and metadata
commands, but no paper-body reading command. The existing requests, Click,
JSON-output convention and shared three-second limiter provide a starting point.

## Minimal proposed interface

Add one PDF-first command, leaving existing commands unchanged:

```bash
arxiv --no-cache text 2410.10813v2 --pages 8-9
arxiv --no-cache text 2410.10813v2 --pages 8-9 -j
```

- Accept one arXiv ID, optionally versioned. Resolve an unversioned ID once via
  metadata and pin the returned version for the entire download/extraction.
- Default to all pages; `--pages` accepts one positive page or an inclusive range.
  Validate bounds and reject malformed ranges. Document PDF physical page
  numbers, which may differ from printed page labels.
- Default output: text with explicit page separators and a compact provenance
  header. `--json-output/-j`: one JSON document on stdout, never progress logs.
- Initially use an optional, locally installed Poppler `pdftotext` backend;
  report its version. Check availability before downloading; provide installation
  guidance on absence, never auto-install. Extract per-page text in layout mode
  so page identity survives conversion. Share timeout/resource budgets across
  the whole extraction rather than giving each page an unlimited budget.
- Reuse metadata lookup and download rate limiting. Store new temporary artifacts
  privately and clean up on completion/failure. Defer persistent extracted-text
  caching and output-file flags; stdout supports deliberate shell redirection.
  Global `--no-cache` retains its existing metadata-cache meaning.

Suggested JSON contract (field names provisional):

```json
{
  "schema_version": 1,
  "status": "ok",
  "paper": {
    "requested_id": "2410.10813v2",
    "resolved_id": "2410.10813v2",
    "title": "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory",
    "source_url": "https://arxiv.org/pdf/2410.10813v2",
    "published": "2024-10-14T17:59:44Z",
    "updated": "2025-03-04T22:19:41Z"
  },
  "extraction": {
    "backend": "pdftotext",
    "backend_version": "<detected version>",
    "source_sha256": "<computed digest>",
    "retrieved_at": "<UTC timestamp>",
    "total_pages": 1,
    "selected_pages": [1]
  },
  "pages": [{"page": 1, "text": "<extracted text>", "citation_url": "https://arxiv.org/pdf/2410.10813v2#page=1"}],
  "warnings": [],
  "error": null
}
```

The page count/text above are illustrative placeholders, not a claim about this
paper. Carry complete authors from metadata as well. Preserve the source hash
and resolved version even when warnings occur. A page link is a navigation hint,
not proof that extracted text faithfully represents a table or formula.

## Fidelity, warnings and failure behavior

Use stable warning/error codes with readable messages and optional page numbers.
Exit 0 for usable output, including warnings (`status: "partial"`); exit nonzero
for fatal failures (`status: "error"`). JSON errors retain the same envelope,
with unavailable fields null and no success-shaped empty response. In text mode,
send diagnostics to stderr. Do not silently label partial text as complete.

Handle missing dependency, download failure, timeout, invalid/encrypted PDF,
parser failure and no extractable text explicitly. Validate response size and
PDF signature before parsing; do not interpret an HTML error page as a PDF.
Capture bounded, sanitized backend stderr. Preserve a nonfatal font warning
alongside usable text; treat a nonzero parser exit as failure even if it wrote
partial output. Flag empty pages without assuming every blank page is scanned.
An entirely empty extraction should explain that an image-only/scanned document
may need OCR; OCR is outside this scope.

Layout mode is only a best effort. Columns can interleave, tables can lose cell
relationships, and equations/symbols can corrupt. Include a fidelity warning in
output and direct users to the original PDF for visual verification. Do not
invent section boundaries or numeric table data. Section labels may be returned
later only when supported by a reliable backend; otherwise omit them. Page
citations are the minimal dependable locator, subject to the stated limitations.

## HTML versus PDF

HTML could preserve explicit section anchors, reading order and semantic tables
better than PDF text. It can also be unavailable for a particular version, or
contain imperfect conversions. HTML coverage was not tested in this trial.
Defer HTML fetching, source selection and automatic fallback to a separate change.
A future HTML backend should record the exact version, URL and section anchor,
sanitize scripts/markup and report missing coverage rather than silently switch
versions or claim PDF-page equivalence. Neither format guarantees faithful
mathematics or tables.

## Acceptance criteria and fixture tests

| Case | Required observable behavior |
|---|---|
| Versioned and unversioned IDs | Pin resolved version; metadata and PDF match; hash and retrieval time emitted. Mock a latest-version change between requests. |
| Two-page text PDF; selected range | Preserve page order and original physical numbers; exact expected fixture text and `#page=N` links; reject zero, reversed and out-of-range selections. |
| Machine output | JSON parses for success, warnings and errors; stdout contains no progress/banner; authors and provenance retained. |
| Font warning with readable text | Exit 0, partial status and bounded diagnostic; no silent warning loss. |
| Dependency absent | Actionable error before network download; no install or environment changes. |
| Scanned, blank or mixed PDF | No-text error for an entirely empty result; page warnings for empty pages in a usable result; no implicit OCR. |
| Malformed, encrypted, oversized PDF; HTML response | Explicit failure; no misleading text; no destination overwrite or leaked temporary artifacts. |
| Backend timeout or nonzero exit | Bounded termination/cleanup, nonzero CLI exit and structured error. |
| Columns, table and equation fixtures | Preserve page provenance and fidelity warning; no assertion of semantic accuracy beyond checked fixture expectations. |
| Untrusted ID, redirects and document content | Reject arbitrary URLs/path traversal; no shell interpolation, unexpected hosts, code execution or instruction following. |

Use tiny generated or redistributable fixtures and mocked HTTP/backend calls for
normal tests. A separately opted-in public-paper smoke check can verify real
integration without making network access a unit-test requirement. No parser or
backend tests are added by this documentation-only proposal.

## Privacy and security boundaries

Treat PDFs, extracted text and embedded instructions as untrusted data. Invoke the
backend with an argument list (`shell=False`), bounded time/output/file sizes and
least privilege; do not execute links, attachments, JavaScript, TeX or paper code.
Validate arXiv IDs (including supported legacy IDs), HTTPS sources and redirect
hosts before requests. Never fetch arbitrary embedded URLs. A parser subprocess
is not itself a sandbox; document platform-specific isolation where available.
Do not upload documents to an extraction service. Avoid logging full paper text,
local paths or credentials; strip control characters from terminal diagnostics.
Keep parser dependencies patched and temporary files private. The first change
should contain only command wiring, provenance/error schema, the PDF adapter,
fixtures and documentation—not OCR, semantic table extraction or agent behavior.
