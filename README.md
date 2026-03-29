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

### `journal` — Search by journal reference

```bash
arxiv journal "Physical Review"
```

### `date-range` — Filter by submitted date

```bash
arxiv date-range "machine learning" --from 20240101 --to 20241231
```

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

## Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--no-cache` | Disable response caching |

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
- Caching: 24-hour TTL in `~/.arxiv_cache/`
- Retry handling: exponential backoff on transient failures

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -x --tb=short
python -m arxiv --help
```

## License

MIT
