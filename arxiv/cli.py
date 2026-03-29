"""CLI entry point for arXiv paper search."""

import json
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from arxiv.api import ArxivClient

console = Console()

SORT_CHOICES = ["relevance", "submittedDate", "lastUpdatedDate"]
ORDER_CHOICES = ["ascending", "descending"]

CATEGORY_GROUPS = {
    "cs": [
        ("cs.AI", "Artificial Intelligence"),
        ("cs.CL", "Computation and Language"),
        ("cs.CV", "Computer Vision and Pattern Recognition"),
        ("cs.LG", "Machine Learning"),
        ("cs.SE", "Software Engineering"),
        ("cs.CR", "Cryptography and Security"),
        ("cs.DC", "Distributed, Parallel, and Cluster Computing"),
        ("cs.DS", "Data Structures and Algorithms"),
        ("cs.IR", "Information Retrieval"),
        ("cs.MA", "Multiagent Systems"),
        ("cs.NE", "Neural and Evolutionary Computing"),
        ("cs.PL", "Programming Languages"),
        ("cs.RO", "Robotics"),
        ("cs.SI", "Social and Information Networks"),
        ("cs.SY", "Systems and Control"),
    ],
    "math": [
        ("math.CO", "Combinatorics"),
        ("math.OC", "Optimization and Control"),
        ("math.PR", "Probability"),
        ("math.ST", "Statistics Theory"),
        ("math.NA", "Numerical Analysis"),
        ("math.AG", "Algebraic Geometry"),
        ("math.AP", "Analysis of PDEs"),
        ("math.AT", "Algebraic Topology"),
        ("math.CA", "Classical Analysis and ODEs"),
        ("math.CT", "Category Theory"),
        ("math.DG", "Differential Geometry"),
        ("math.DS", "Dynamical Systems"),
        ("math.FA", "Functional Analysis"),
        ("math.GM", "General Mathematics"),
        ("math.GN", "General Topology"),
        ("math.GR", "Group Theory"),
        ("math.GT", "Geometric Topology"),
        ("math.HO", "History and Overview"),
        ("math.IT", "Information Theory"),
        ("math.KT", "K-Theory and Homology"),
        ("math.LO", "Logic"),
        ("math.MG", "Metric Geometry"),
        ("math.MP", "Mathematical Physics"),
        ("math.NT", "Number Theory"),
        ("math.OA", "Operator Algebras"),
        ("math.QA", "Quantum Algebra"),
        ("math.RA", "Rings and Algebras"),
        ("math.RT", "Representation Theory"),
        ("math.SG", "Symplectic Geometry"),
        ("math.SP", "Spectral Theory"),
    ],
    "stat": [
        ("stat.ML", "Machine Learning"),
        ("stat.ME", "Methodology"),
        ("stat.AP", "Applications"),
        ("stat.CO", "Computation"),
        ("stat.TH", "Statistics Theory"),
    ],
    "physics": [
        ("astro-ph", "Astrophysics"),
        ("cond-mat", "Condensed Matter"),
        ("gr-qc", "General Relativity and Quantum Cosmology"),
        ("hep-ph", "High Energy Physics - Phenomenology"),
        ("hep-th", "High Energy Physics - Theory"),
        ("math-ph", "Mathematical Physics"),
        ("nucl-th", "Nuclear Theory"),
        ("quant-ph", "Quantum Physics"),
    ],
    "eess": [
        ("eess.AS", "Audio and Speech Processing"),
        ("eess.IV", "Image and Video Processing"),
        ("eess.SP", "Signal Processing"),
        ("eess.SY", "Systems and Control"),
    ],
    "q-bio": [
        ("q-bio.BM", "Biomolecules"),
        ("q-bio.CB", "Cell Behavior"),
        ("q-bio.GN", "Genomics"),
        ("q-bio.NC", "Neurons and Cognition"),
        ("q-bio.QM", "Quantitative Methods"),
    ],
    "q-fin": [
        ("q-fin.CP", "Computational Finance"),
        ("q-fin.EC", "Economics"),
        ("q-fin.GN", "General Finance"),
        ("q-fin.PM", "Portfolio Management"),
        ("q-fin.ST", "Statistical Finance"),
    ],
    "econ": [
        ("econ.EM", "Econometrics"),
        ("econ.GN", "General Economics"),
        ("econ.TH", "Theoretical Economics"),
    ],
}


def _error_exit(result: dict) -> bool:
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)
    return False


def _truncate(text: str, width: int = 50) -> str:
    if not text:
        return ""
    return text if len(text) <= width else f"{text[:width - 3]}..."


def _format_date(value: str) -> str:
    if not value:
        return ""
    return value[:10]


def _format_authors_short(authors: list) -> str:
    names = [a.get("name", "") for a in authors if a.get("name")]
    if not names:
        return ""
    if len(names) <= 2:
        return ", ".join(names)
    return f"{names[0]}, {names[1]}, et al."


def _format_authors_full(authors: list) -> str:
    if not authors:
        return "N/A"
    lines = []
    for author in authors:
        name = author.get("name", "").strip()
        affiliation = author.get("affiliation", "").strip()
        if affiliation:
            lines.append(f"{name} ({affiliation})")
        else:
            lines.append(name)
    return "\n".join(line for line in lines if line)


def _escape_markdown_cell(text: str) -> str:
    return (text or "").replace("|", "\\|")


def _render_papers(result: dict, title: str) -> None:
    papers = result.get("papers", [])
    total = result.get("total", len(papers))
    start = result.get("start", 0)

    if not papers:
        console.print(f"[yellow]No results for {title}[/yellow]")
        return

    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Authors", style="green")
    table.add_column("Category", style="magenta")
    table.add_column("Published", style="yellow")

    for paper in papers:
        categories = paper.get("categories", [])
        table.add_row(
            paper.get("id", ""),
            _truncate(paper.get("title", ""), 50),
            _format_authors_short(paper.get("authors", [])),
            paper.get("primary_category") or (categories[0] if categories else ""),
            _format_date(paper.get("published", "")),
        )

    console.print(table)
    end = start + len(papers)
    console.print(f"[dim]Showing {start + 1}-{end} of {total} total papers[/dim]")


def _render_papers_markdown(result: dict, title: str) -> None:
    papers = result.get("papers", [])
    total = result.get("total", len(papers))
    start = result.get("start", 0)

    click.echo(f"## {title}")
    click.echo("")
    click.echo("| ID | Title | Authors | Category | Published |")
    click.echo("|---|---|---|---|---|")
    for paper in papers:
        categories = paper.get("categories", [])
        paper_id = _escape_markdown_cell(paper.get("id", ""))
        paper_title = _escape_markdown_cell(_truncate(paper.get("title", ""), 50))
        paper_authors = _escape_markdown_cell(_format_authors_short(paper.get("authors", [])))
        paper_category = _escape_markdown_cell(paper.get("primary_category") or (categories[0] if categories else ""))
        paper_published = _escape_markdown_cell(_format_date(paper.get("published", "")))
        click.echo(f"| {paper_id} | {paper_title} | {paper_authors} | {paper_category} | {paper_published} |")
    end = start + len(papers)
    click.echo("")
    click.echo(f"Showing {start + 1}-{end} of {total} total papers")


def _render_paper_detail(paper: dict) -> None:
    categories = ", ".join(paper.get("categories", [])) or "N/A"
    lines = [
        f"[bold]ID:[/bold] {paper.get('id', 'N/A')}",
        f"[bold]Title:[/bold] {paper.get('title', 'N/A')}",
        f"[bold]Authors:[/bold]\n{_format_authors_full(paper.get('authors', []))}",
        f"[bold]Categories:[/bold] {categories}",
        f"[bold]Published:[/bold] {_format_date(paper.get('published', ''))}",
        f"[bold]Updated:[/bold] {_format_date(paper.get('updated', ''))}",
        f"[bold]PDF:[/bold] {paper.get('pdf_url') or 'N/A'}",
        f"[bold]DOI:[/bold] {paper.get('doi') or 'N/A'}",
        f"[bold]Journal Ref:[/bold] {paper.get('journal_ref') or 'N/A'}",
        f"[bold]Comment:[/bold] {paper.get('comment') or 'N/A'}",
        "",
        "[bold]Abstract:[/bold]",
        paper.get("summary", "N/A"),
    ]
    console.print(Panel("\n".join(lines), title="Paper Details", expand=False))


def _render_paper_detail_markdown(paper: dict) -> None:
    categories = ", ".join(paper.get("categories", [])) or "N/A"
    click.echo(f"## {paper.get('title', 'Paper')}")
    click.echo("")
    click.echo(f"- **ID:** {paper.get('id', 'N/A')}")
    click.echo(f"- **Authors:** {_format_authors_full(paper.get('authors', [])).replace(chr(10), '; ')}")
    click.echo(f"- **Categories:** {categories}")
    click.echo(f"- **Published:** {_format_date(paper.get('published', ''))}")
    click.echo(f"- **Updated:** {_format_date(paper.get('updated', ''))}")
    click.echo(f"- **PDF:** {paper.get('pdf_url') or 'N/A'}")
    click.echo(f"- **DOI:** {paper.get('doi') or 'N/A'}")
    click.echo(f"- **Journal Ref:** {paper.get('journal_ref') or 'N/A'}")
    click.echo(f"- **Comment:** {paper.get('comment') or 'N/A'}")
    click.echo("")
    click.echo("### Abstract")
    click.echo("")
    click.echo(paper.get("summary", "N/A"))


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--no-cache", is_flag=True, help="Disable response caching")
@click.pass_context
def main(ctx, debug, no_cache):
    """arXiv CLI — Academic paper search and research intelligence tool."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING)
    ctx.ensure_object(dict)
    ctx.obj["client"] = ArxivClient(use_cache=not no_cache)


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, show_default=True, help="Number of results")
@click.option("--offset", "-o", default=0, show_default=True, help="Start offset")
@click.option("--sort", type=click.Choice(SORT_CHOICES), default="relevance", show_default=True)
@click.option("--order", type=click.Choice(ORDER_CHOICES), default="descending", show_default=True)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table")
@click.pass_context
def search(ctx, query, limit, offset, sort, order, json_output, markdown):
    """Search arXiv papers."""
    client = ctx.obj["client"]
    result = client.search(query, start=offset, max_results=limit, sort_by=sort, sort_order=order)
    if _error_exit(result):
        return
    if json_output:
        click.echo(json.dumps(result, indent=2))
    elif markdown:
        _render_papers_markdown(result, f"Search: {query}")
    else:
        _render_papers(result, f"Search: {query}")


@main.command()
@click.argument("arxiv_ids", nargs=-1, required=True)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown")
@click.pass_context
def lookup(ctx, arxiv_ids, json_output, markdown):
    """Look up one or more papers by arXiv ID."""
    client = ctx.obj["client"]
    result = client.search_by_ids(list(arxiv_ids))
    if _error_exit(result):
        return
    papers = result.get("papers", [])

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    if len(papers) == 1:
        if markdown:
            _render_paper_detail_markdown(papers[0])
        else:
            _render_paper_detail(papers[0])
        return

    if markdown:
        _render_papers_markdown(result, f"Lookup: {', '.join(arxiv_ids)}")
    else:
        _render_papers(result, f"Lookup: {', '.join(arxiv_ids)}")


@main.command()
@click.argument("name")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--offset", "-o", default=0, show_default=True)
@click.option("--sort", type=click.Choice(SORT_CHOICES), default="submittedDate", show_default=True)
@click.option("--order", type=click.Choice(ORDER_CHOICES), default="descending", show_default=True)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table")
@click.pass_context
def author(ctx, name, limit, offset, sort, order, json_output, markdown):
    """Search by author name."""
    client = ctx.obj["client"]
    result = client.search_by_author(name, start=offset, max_results=limit, sort_by=sort, sort_order=order)
    if _error_exit(result):
        return
    if json_output:
        click.echo(json.dumps(result, indent=2))
    elif markdown:
        _render_papers_markdown(result, f"Author: {name}")
    else:
        _render_papers(result, f"Author: {name}")


@main.command()
@click.argument("category_code")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--offset", "-o", default=0, show_default=True)
@click.option("--sort", type=click.Choice(SORT_CHOICES), default="submittedDate", show_default=True)
@click.option("--order", type=click.Choice(ORDER_CHOICES), default="descending", show_default=True)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table")
@click.pass_context
def category(ctx, category_code, limit, offset, sort, order, json_output, markdown):
    """Search by arXiv category code."""
    client = ctx.obj["client"]
    result = client.search_by_category(
        category_code,
        start=offset,
        max_results=limit,
        sort_by=sort,
        sort_order=order,
    )
    if _error_exit(result):
        return
    if json_output:
        click.echo(json.dumps(result, indent=2))
    elif markdown:
        _render_papers_markdown(result, f"Category: {category_code}")
    else:
        _render_papers(result, f"Category: {category_code}")


@main.command()
@click.argument("category_code")
@click.option("--limit", "-n", default=20, show_default=True, help="Number of results")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table")
@click.pass_context
def recent(ctx, category_code, limit, json_output, markdown):
    """Get recent papers in a category."""
    client = ctx.obj["client"]
    result = client.search_by_category(
        category_code,
        start=0,
        max_results=limit,
        sort_by="submittedDate",
        sort_order="descending",
    )
    if _error_exit(result):
        return
    if json_output:
        click.echo(json.dumps(result, indent=2))
    elif markdown:
        _render_papers_markdown(result, f"Recent in {category_code}")
    else:
        _render_papers(result, f"Recent in {category_code}")


@main.command()
@click.argument("arxiv_id")
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown")
@click.pass_context
def abstract(ctx, arxiv_id, json_output, markdown):
    """Show full abstract for a paper by ID."""
    client = ctx.obj["client"]
    result = client.search_by_id(arxiv_id)
    if _error_exit(result):
        return

    papers = result.get("papers", [])
    if not papers:
        console.print(f"[yellow]No paper found for ID {arxiv_id}[/yellow]")
        raise SystemExit(1)

    paper = papers[0]
    if json_output:
        click.echo(json.dumps(paper, indent=2))
    elif markdown:
        _render_paper_detail_markdown(paper)
    else:
        _render_paper_detail(paper)


@main.command()
@click.argument("arxiv_id")
@click.option("--output", "-o", default=None, help="Output file path or directory")
@click.pass_context
def download(ctx, arxiv_id, output):
    """Download a paper PDF by arXiv ID."""
    client = ctx.obj["client"]

    output_path = None
    if output:
        target = Path(output).expanduser()
        safe_id = arxiv_id.replace("/", "_")
        if target.exists() and target.is_dir():
            output_path = str(target / f"{safe_id}.pdf")
        elif output.endswith("/") or output.endswith("\\"):
            target.mkdir(parents=True, exist_ok=True)
            output_path = str(target / f"{safe_id}.pdf")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            output_path = str(target)

    try:
        saved_path = client.download_pdf(arxiv_id, output_path=output_path)
        console.print(f"[green]Downloaded:[/green] {saved_path}")
    except Exception as exc:
        console.print(f"[red]Download failed:[/red] {exc}")
        raise SystemExit(1) from exc


@main.command()
@click.argument("journal_name")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--offset", "-o", default=0, show_default=True)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table")
@click.pass_context
def journal(ctx, journal_name, limit, offset, json_output, markdown):
    """Search papers by journal reference."""
    client = ctx.obj["client"]
    result = client.search_by_journal(journal_name, start=offset, max_results=limit)
    if _error_exit(result):
        return
    if json_output:
        click.echo(json.dumps(result, indent=2))
    elif markdown:
        _render_papers_markdown(result, f"Journal: {journal_name}")
    else:
        _render_papers(result, f"Journal: {journal_name}")


@main.command(name="date-range")
@click.argument("query")
@click.option("--from", "date_from", required=True, help="Start date YYYYMMDD")
@click.option("--to", "date_to", required=True, help="End date YYYYMMDD")
@click.option("--limit", "-n", default=10, show_default=True)
@click.option("--offset", "-o", default=0, show_default=True)
@click.option("--json-output", "-j", is_flag=True, help="Output raw JSON")
@click.option("--markdown", "-m", is_flag=True, help="Output as markdown table")
@click.pass_context
def date_range(ctx, query, date_from, date_to, limit, offset, json_output, markdown):
    """Search papers in a submitted date range."""
    client = ctx.obj["client"]
    result = client.search_with_date_range(
        query,
        date_from=date_from,
        date_to=date_to,
        start=offset,
        max_results=limit,
    )
    if _error_exit(result):
        return
    if result.get("fallback") == "client_side_date_filter":
        console.print("[yellow]Date-range fallback used: client-side date filtering after upstream 429[/yellow]")
    if json_output:
        click.echo(json.dumps(result, indent=2))
    elif markdown:
        _render_papers_markdown(result, f"Date range: {query} ({date_from}-{date_to})")
    else:
        _render_papers(result, f"Date range: {query} ({date_from}-{date_to})")


@main.command()
@click.option("--filter", "group_filter", default=None, help="Filter category group prefix")
def categories(group_filter):
    """List common arXiv category codes."""
    groups = CATEGORY_GROUPS
    if group_filter:
        group_filter = group_filter.strip()
        groups = {k: v for k, v in CATEGORY_GROUPS.items() if k.startswith(group_filter)}

    if not groups:
        console.print(f"[yellow]No category group matching '{group_filter}'[/yellow]")
        return

    table = Table(title="Common arXiv Categories")
    table.add_column("Group", style="cyan")
    table.add_column("Code", style="magenta")
    table.add_column("Name", style="white")

    for group, categories_list in groups.items():
        for code, name in categories_list:
            table.add_row(group, code, name)
    console.print(table)


@main.command(name="clear-cache")
@click.pass_context
def clear_cache(ctx):
    """Clear local response cache."""
    client = ctx.obj["client"]
    if not client.cache:
        console.print("[yellow]Cache is disabled for this run (--no-cache).[/yellow]")
        return
    removed = client.cache.clear()
    console.print(f"[green]Cleared {removed} cached response files[/green]")


if __name__ == "__main__":
    main()
