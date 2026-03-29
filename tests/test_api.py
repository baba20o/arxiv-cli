"""Tests for arXiv API client."""

from arxiv.api import ArxivClient


def test_client_init():
    c = ArxivClient(use_cache=False)
    assert c.use_cache is False


def test_client_init_with_cache():
    c = ArxivClient(use_cache=True)
    assert c.use_cache is True
