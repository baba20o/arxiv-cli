"""CLI entry point for arXiv paper search."""

import logging

import click

from arxiv.api import ArxivClient


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--no-cache", is_flag=True, help="Disable response caching")
@click.pass_context
def main(ctx, debug, no_cache):
    """arXiv CLI — Academic paper search and research intelligence tool.

    Search, retrieve, and analyze papers from arXiv.org.
    No API key required.
    """
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)
    ctx.ensure_object(dict)
    ctx.obj["client"] = ArxivClient(use_cache=not no_cache)


@main.command()
@click.argument("query")
def search(ctx, query):
    """Search arXiv papers. (placeholder)"""
    click.echo(f"Search placeholder: {query}")


if __name__ == "__main__":
    main()
