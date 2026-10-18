# arXiv CLI

A command-line tool for searching and retrieving arXiv papers via the public [arXiv API](https://info.arxiv.org/help/api/user-manual.html).

Built for research agents and human analysts with rich terminal output, markdown tables, and raw JSON.

## Install

```bash
pip install -e .
```

## Setup

No API key is required.

## Commands

### `search` — Full-text search

```bash
arxiv search "transformer attention mechanism"
arxiv search "ti:attention AND au:vaswani"
arxiv search "cat:cs.AI AND abs:reinforcement learning" --limit 20
```

### `lookup` — Lookup by arXiv ID

```bash
arxiv lookup 2103.12345
arxiv lookup 2103.12345 2201.54321
```

### `author` — Search by author

```bash
arxiv author "Yann LeCun"
arxiv author "hinton" --limit 20
```

### `category` — Search in category

```bash
arxiv category cs.AI
arxiv category stat.ML --limit 20
```

### `recent` — Latest papers by category

```bash
arxiv recent cs.LG
arxiv recent math.CO --limit 25
```

### `abstract` — Show full abstract by ID

```bash
arxiv abstract 1706.03762
```

### `download` — Download PDF

```bash
arxiv download 1706.03762
arxiv download 1706.03762 --output ./papers/
arxiv download 1706.03762 --output ./papers/attention.pdf
```

Without `--output`, the PDF is saved in the current directory as `<id>.pdf` (a `/` in old-style IDs becomes `_`). An `--output` value that is an existing directory, or that ends in `/`, is treated as a directory and created if needed; any other value is used as the file path. An existing file at that path is overwritten without prompting.

### `journal` — Search by journal reference

```bash
arxiv journal "Physical Review"
```

### `date-range` — Filter by submitted date

```bash
arxiv date-range "machine learning" --from 20240101 --to 20241231
```

`--from` and `--to` are required and use `YYYYMMDD`. If arXiv still rate-limits the date-filtered query (HTTP 429) after retries, the CLI prints a warning, re-runs the query without the date filter, and filters locally by each paper's `published` (first version) date. This fallback only inspects the most recent matches (the larger of 100 or 8× `--limit`, at most 2000), so it can miss older papers in the range and its total counts only matches within that pool. JSON output marks these results with `"fallback": "client_side_date_filter"`. If the fallback query also fails, the original error is reported.

### `categories` — List category codes

```bash
arxiv categories
arxiv categories --filter cs
```

### `clear-cache` — Remove cached API responses

```bash
arxiv clear-cache
```

## Output Formats

Every search-style command supports three output modes:

| Flag | Format | Use case |
|------|--------|----------|
| *(default)* | Rich terminal tables/panels | Human terminal use |
| `--markdown` / `-m` | Markdown output | Agent parsing, copy/paste |
| `--json-output` / `-j` | Raw JSON | Programmatic pipelines |

## Paging and Sorting

| Option | Commands | Default |
|--------|----------|---------|
| `--limit` / `-n` | `search`, `author`, `category`, `recent`, `journal`, `date-range` | 10 (20 for `recent`) |
| `--offset` / `-o` | `search`, `author`, `category`, `journal`, `date-range` | 0 |
| `--sort` | `search`, `author`, `category` | `relevance` for `search`, `submittedDate` otherwise; also `lastUpdatedDate` |
| `--order` | `search`, `author`, `category` | `descending` (or `ascending`) |

```bash
arxiv search "ti:diffusion" --sort submittedDate --limit 5 --offset 5
```

On `download`, `-o` is short for `--output`, not `--offset`.

## Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--no-cache` | Disable response caching |

Global options go before the command name:

```bash
arxiv --no-cache search "transformer attention mechanism"
```

## Query Syntax

arXiv search supports fielded queries and boolean operators:

| Syntax | Example |
|--------|---------|
| Full text | `transformer architecture` |
| Title field | `ti:attention` |
| Author field | `au:vaswani` |
| Abstract field | `abs:diffusion model` |
| Category field | `cat:cs.LG` |
| Journal field | `jr:Physical Review` |
| Boolean | `ti:attention AND au:vaswani` |
| Negation | `cat:cs.LG ANDNOT abs:survey` |
| Date range | `submittedDate:[202401010000 TO 202412312359]` |

## Architecture

```
arxiv/
├── cli.py           # Click commands + Rich/Markdown renderers
├── api.py           # arXiv Atom API client + XML parsing
├── cache.py         # File-based cache (~/.arxiv_cache/)
├── rate_limiter.py  # Shared SQLite limiter (~/.arxiv/rate_limit.db)
├── __init__.py
└── __main__.py
```

- Rate limiting: 1 request every 3 seconds across processes
- Caching: successful API query responses are cached for 24 hours in `~/.arxiv_cache/`; PDF downloads are not cached
- Retry handling: API queries retry up to 3 times with exponential backoff on HTTP errors and network failures (429/503 responses honor `Retry-After`); PDF downloads are not retried

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -x --tb=short
python -m arxiv --help
```

## License

MIT
