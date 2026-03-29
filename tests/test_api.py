"""Tests for arXiv API client."""

import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

from arxiv.api import ArxivClient, _parse_entry, _parse_response


@pytest.fixture
def client():
    return ArxivClient(use_cache=False)


def test_client_init():
    c = ArxivClient(use_cache=False)
    assert c.use_cache is False
    assert c.cache is None
    assert c.rate_limiter is not None


def test_client_init_with_cache():
    c = ArxivClient(use_cache=True)
    assert c.use_cache is True
    assert c.cache is not None


@patch("arxiv.api.ArxivClient._query")
def test_search(mock_query, client):
    mock_query.return_value = {"total": 0, "papers": []}
    client.search("transformer", start=5, max_results=15, sort_by="submittedDate", sort_order="ascending")
    mock_query.assert_called_once_with({
        "search_query": "transformer",
        "start": 5,
        "max_results": 15,
        "sortBy": "submittedDate",
        "sortOrder": "ascending",
    })


@patch("arxiv.api.ArxivClient._query")
def test_search_by_id(mock_query, client):
    mock_query.return_value = {"total": 1, "papers": []}
    client.search_by_id("2103.12345")
    mock_query.assert_called_once_with({
        "id_list": "2103.12345",
        "max_results": 1,
    })


@patch("arxiv.api.ArxivClient._query")
def test_search_by_ids(mock_query, client):
    mock_query.return_value = {"total": 2, "papers": []}
    client.search_by_ids(["2103.12345", "2201.54321"])
    mock_query.assert_called_once_with({
        "id_list": "2103.12345,2201.54321",
        "max_results": 2,
    })


def test_search_by_author(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_by_author("Yann LeCun", start=2, max_results=7, sort_by="relevance", sort_order="ascending")
        mock_search.assert_called_once_with(
            "au:Yann LeCun",
            start=2,
            max_results=7,
            sort_by="relevance",
            sort_order="ascending",
        )


def test_search_by_title(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_by_title("attention")
        mock_search.assert_called_once_with(
            "ti:attention",
            start=0,
            max_results=10,
            sort_by="relevance",
            sort_order="descending",
        )


def test_search_by_abstract(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_by_abstract("reinforcement learning")
        mock_search.assert_called_once_with(
            "abs:reinforcement learning",
            start=0,
            max_results=10,
            sort_by="relevance",
            sort_order="descending",
        )


def test_search_by_category(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_by_category("cs.AI", start=10, max_results=5)
        mock_search.assert_called_once_with(
            "cat:cs.AI",
            start=10,
            max_results=5,
            sort_by="submittedDate",
            sort_order="descending",
        )


def test_search_by_journal(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_by_journal("Nature")
        mock_search.assert_called_once_with(
            "jr:Nature",
            start=0,
            max_results=10,
            sort_by="submittedDate",
            sort_order="descending",
        )


def test_search_with_date_range(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_with_date_range("machine learning", "20240101", "20241231", start=1, max_results=9)
        mock_search.assert_called_once_with(
            "machine learning AND submittedDate:[202401010000 TO 202412312359]",
            start=1,
            max_results=9,
            sort_by="submittedDate",
            sort_order="descending",
        )


def test_search_author_in_category(client):
    with patch.object(client, "search", return_value={"total": 0, "papers": []}) as mock_search:
        client.search_author_in_category("hinton", "cs.LG", start=3, max_results=4)
        mock_search.assert_called_once_with(
            "au:hinton AND cat:cs.LG",
            start=3,
            max_results=4,
            sort_by="submittedDate",
            sort_order="descending",
        )


def test_parse_entry():
    entry_xml = f"""
    <entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <id>http://arxiv.org/abs/1706.03762v7</id>
      <updated>2023-01-01T00:00:00Z</updated>
      <published>2017-06-12T17:57:00Z</published>
      <title>  Attention   Is All You Need  </title>
      <summary> Transformer architecture paper. </summary>
      <author>
        <name>Ashish Vaswani</name>
        <arxiv:affiliation>Google</arxiv:affiliation>
      </author>
      <author>
        <name>Noam Shazeer</name>
      </author>
      <link rel="alternate" href="http://arxiv.org/abs/1706.03762v7" />
      <link title="pdf" href="http://arxiv.org/pdf/1706.03762v7" />
      <arxiv:doi>10.1000/test-doi</arxiv:doi>
      <arxiv:journal_ref>NIPS 2017</arxiv:journal_ref>
      <arxiv:comment>Accepted at NIPS</arxiv:comment>
      <arxiv:primary_category term="cs.CL" />
      <category term="cs.CL" />
      <category term="cs.LG" />
    </entry>
    """
    entry = ET.fromstring(entry_xml)
    paper = _parse_entry(entry)
    assert paper["id"] == "1706.03762v7"
    assert paper["title"] == "Attention Is All You Need"
    assert paper["summary"] == "Transformer architecture paper."
    assert paper["authors"][0]["name"] == "Ashish Vaswani"
    assert paper["authors"][0]["affiliation"] == "Google"
    assert paper["pdf_url"] == "http://arxiv.org/pdf/1706.03762v7"
    assert paper["categories"] == ["cs.CL", "cs.LG"]
    assert paper["primary_category"] == "cs.CL"
    assert paper["journal_ref"] == "NIPS 2017"
    assert paper["doi"] == "10.1000/test-doi"


def test_parse_response():
    xml = """
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
          xmlns:arxiv="http://arxiv.org/schemas/atom">
      <opensearch:totalResults>1</opensearch:totalResults>
      <opensearch:startIndex>0</opensearch:startIndex>
      <opensearch:itemsPerPage>1</opensearch:itemsPerPage>
      <entry>
        <id>http://arxiv.org/abs/2401.00001</id>
        <updated>2024-01-01T00:00:00Z</updated>
        <published>2024-01-01T00:00:00Z</published>
        <title>Test Paper</title>
        <summary>Test summary</summary>
        <author><name>Test Author</name></author>
        <arxiv:primary_category term="cs.AI" />
        <category term="cs.AI" />
      </entry>
    </feed>
    """
    result = _parse_response(xml)
    assert result["total"] == 1
    assert result["start"] == 0
    assert result["page_size"] == 1
    assert len(result["papers"]) == 1
    assert result["papers"][0]["id"] == "2401.00001"


def test_error_response():
    xml = """
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
      <opensearch:totalResults>0</opensearch:totalResults>
      <entry>
        <id>http://arxiv.org/api/errors#bad_query</id>
        <summary>Bad query syntax</summary>
      </entry>
    </feed>
    """
    result = _parse_response(xml)
    assert result["error"] == "Bad query syntax"
    assert result["papers"] == []
    assert result["total"] == 0
