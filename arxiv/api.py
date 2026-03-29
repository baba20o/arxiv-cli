"""arXiv API client.

Base URL: http://export.arxiv.org/api/query
Auth: None required
Rate limit: 1 request per 3 seconds
Response: Atom 1.0 XML
Docs: https://info.arxiv.org/help/api/user-manual.html
"""

import logging
import random
import time
import xml.etree.ElementTree as ET
from typing import List

import requests

from arxiv.cache import PaperCache
from arxiv.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

BASE_URL = "http://export.arxiv.org/api/query"

ATOM_NS = "{http://www.w3.org/2005/Atom}"
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

MAX_RETRIES = 3
DEFAULT_RETRY_WAIT = 5
MAX_RETRY_WAIT = 120
REQUEST_TIMEOUT = 45
DATE_RANGE_FALLBACK_MIN = 100
DATE_RANGE_FALLBACK_MULTIPLIER = 8


def _text(el, tag: str, ns: str = ATOM_NS) -> str:
    """Extract text from a child element, or empty string."""
    child = el.find(f"{ns}{tag}")
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _parse_entry(entry) -> dict:
    """Parse a single Atom entry into a dict."""
    paper = {}

    # ID — extract arXiv ID from URL
    raw_id = _text(entry, "id")
    paper["id"] = raw_id.replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")
    paper["url"] = raw_id

    paper["title"] = " ".join(_text(entry, "title").split())  # normalize whitespace
    paper["summary"] = _text(entry, "summary").strip()
    paper["published"] = _text(entry, "published")
    paper["updated"] = _text(entry, "updated")

    # Authors
    authors = []
    for author_el in entry.findall(f"{ATOM_NS}author"):
        name = _text(author_el, "name")
        affiliation = _text(author_el, "affiliation", ns=ARXIV_NS)
        if name:
            a = {"name": name}
            if affiliation:
                a["affiliation"] = affiliation
            authors.append(a)
    paper["authors"] = authors

    # Links
    pdf_link = ""
    doi_link = ""
    for link in entry.findall(f"{ATOM_NS}link"):
        title = link.get("title", "")
        href = link.get("href", "")
        if title == "pdf":
            pdf_link = href
        elif title == "doi":
            doi_link = href
    paper["pdf_url"] = pdf_link
    paper["doi_url"] = doi_link

    # Categories
    categories = []
    for cat in entry.findall(f"{ATOM_NS}category"):
        term = cat.get("term", "")
        if term:
            categories.append(term)
    paper["categories"] = categories

    # Primary category
    primary = entry.find(f"{ARXIV_NS}primary_category")
    paper["primary_category"] = primary.get("term", "") if primary is not None else ""

    # Extended metadata
    paper["comment"] = _text(entry, "comment", ns=ARXIV_NS)
    paper["journal_ref"] = _text(entry, "journal_ref", ns=ARXIV_NS)
    paper["doi"] = _text(entry, "doi", ns=ARXIV_NS)

    return paper


def _parse_response(xml_text: str) -> dict:
    """Parse Atom XML response into a structured dict."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return {"error": f"XML parse error: {e}", "papers": [], "total": 0}

    total = 0
    start_index = 0
    items_per_page = 0

    total_el = root.find(f"{OPENSEARCH_NS}totalResults")
    if total_el is not None and total_el.text:
        total = int(total_el.text)

    start_el = root.find(f"{OPENSEARCH_NS}startIndex")
    if start_el is not None and start_el.text:
        start_index = int(start_el.text)

    items_el = root.find(f"{OPENSEARCH_NS}itemsPerPage")
    if items_el is not None and items_el.text:
        items_per_page = int(items_el.text)

    papers = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        # Check for error entries
        entry_id = _text(entry, "id")
        if "api/errors" in entry_id:
            error_msg = _text(entry, "summary")
            return {"error": error_msg, "papers": [], "total": 0}
        papers.append(_parse_entry(entry))

    return {
        "total": total,
        "start": start_index,
        "page_size": items_per_page,
        "papers": papers,
    }


def _normalize_yyyymmdd(date_text: str) -> str:
    if not date_text:
        return ""
    compact = date_text[:10].replace("-", "")
    if len(compact) != 8 or not compact.isdigit():
        return ""
    return compact


def _retry_wait_seconds(attempt: int, response: requests.Response = None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, float(retry_after))
            except ValueError:
                pass

    base = 15 if response is not None and response.status_code == 429 else DEFAULT_RETRY_WAIT
    wait = base * (2 ** attempt) + random.uniform(0, 1.0)
    return min(wait, MAX_RETRY_WAIT)


class ArxivClient:
    """Client for the arXiv API."""

    def __init__(self, use_cache: bool = True):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "arxiv-cli/0.1.0",
        })
        self.rate_limiter = get_rate_limiter()
        self.use_cache = use_cache
        self.cache = PaperCache() if use_cache else None

    # ── Search ────────────────────────────────────────────

    def search(
        self,
        query: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> dict:
        """Search papers with full query syntax.

        Query supports field prefixes: ti:, au:, abs:, co:, jr:, cat:, rn:, all:
        Boolean operators: AND, OR, ANDNOT
        Exact phrases: "quantum computing"
        """
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        return self._query(params)

    def search_by_ids(self, id_list: List[str]) -> dict:
        """Retrieve papers by arXiv IDs.

        IDs can include version: 2103.12345v2
        """
        params = {
            "id_list": ",".join(id_list),
            "max_results": len(id_list),
        }
        return self._query(params)

    def search_by_id(self, arxiv_id: str) -> dict:
        """Retrieve a single paper by arXiv ID."""
        return self.search_by_ids([arxiv_id])

    # ── Field-Targeted Searches ───────────────────────────

    def search_by_author(
        self,
        author: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> dict:
        """Search papers by author name."""
        query = f"au:{author}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by=sort_by, sort_order=sort_order)

    def search_by_title(
        self,
        title: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> dict:
        """Search papers by title."""
        query = f"ti:{title}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by=sort_by, sort_order=sort_order)

    def search_by_abstract(
        self,
        abstract_query: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "relevance",
        sort_order: str = "descending",
    ) -> dict:
        """Search within paper abstracts."""
        query = f"abs:{abstract_query}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by=sort_by, sort_order=sort_order)

    def search_by_category(
        self,
        category: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> dict:
        """Search papers in a specific category."""
        query = f"cat:{category}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by=sort_by, sort_order=sort_order)

    def search_by_journal(
        self,
        journal: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> dict:
        """Search papers by journal reference."""
        query = f"jr:{journal}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by=sort_by, sort_order=sort_order)

    def search_with_date_range(
        self,
        query: str,
        date_from: str,
        date_to: str,
        start: int = 0,
        max_results: int = 10,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> dict:
        """Search papers within a date range.

        Dates in YYYYMMDD format. Appends submittedDate range filter.
        """
        date_filter = f"submittedDate:[{date_from}0000 TO {date_to}2359]"
        full_query = f"{query} AND {date_filter}" if query else date_filter
        result = self.search(
            full_query,
            start=start,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        if "error" not in result or "429" not in str(result.get("error", "")) or not query:
            return result

        logger.warning(
            "Date-range query received 429; retrying via client-side date filtering for query: %s",
            query,
        )
        fallback_limit = min(2000, max(DATE_RANGE_FALLBACK_MIN, max_results * DATE_RANGE_FALLBACK_MULTIPLIER))
        fallback = self.search(
            query,
            start=0,
            max_results=fallback_limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        if "error" in fallback:
            return result

        filtered = [
            paper
            for paper in fallback.get("papers", [])
            if date_from <= _normalize_yyyymmdd(paper.get("published", "")) <= date_to
        ]
        window = filtered[start:start + max_results]
        return {
            "total": len(filtered),
            "start": start,
            "page_size": len(window),
            "papers": window,
            "fallback": "client_side_date_filter",
        }

    # ── Compound Queries ──────────────────────────────────

    def search_author_in_category(
        self,
        author: str,
        category: str,
        start: int = 0,
        max_results: int = 10,
    ) -> dict:
        """Search for an author's papers in a specific category."""
        query = f"au:{author} AND cat:{category}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by="submittedDate", sort_order="descending")

    def search_title_in_category(
        self,
        title_query: str,
        category: str,
        start: int = 0,
        max_results: int = 10,
    ) -> dict:
        """Search titles within a specific category."""
        query = f"ti:{title_query} AND cat:{category}"
        return self.search(query, start=start, max_results=max_results,
                          sort_by="relevance", sort_order="descending")

    # ── PDF Download ──────────────────────────────────────

    def download_pdf(self, arxiv_id: str, output_path: str = None) -> str:
        """Download a paper's PDF.

        Returns the path to the downloaded file.
        """
        # Normalize ID
        clean_id = arxiv_id.replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

        if not output_path:
            safe_id = clean_id.replace("/", "_")
            output_path = f"{safe_id}.pdf"

        self.rate_limiter.acquire()
        response = self.session.get(pdf_url, stream=True, timeout=(10, REQUEST_TIMEOUT))
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return output_path

    # ── Internal ──────────────────────────────────────────

    def _query(self, params: dict) -> dict:
        """Execute an API query with caching and rate limiting."""
        cache_key = BASE_URL
        cache_params = {k: str(v) for k, v in params.items()}

        if self.use_cache and self.cache:
            cached = self.cache.get(cache_key, cache_params)
            if cached is not None:
                logger.debug("Cache hit: %s", params)
                return cached

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            self.rate_limiter.acquire()
            try:
                response = self.session.get(BASE_URL, params=params, timeout=(10, REQUEST_TIMEOUT))

                if response.status_code in (429, 503):
                    wait = _retry_wait_seconds(attempt, response)
                    if attempt < MAX_RETRIES:
                        logger.warning(
                            "arXiv %d — waiting %.1fs (retry %d/%d)",
                            response.status_code,
                            wait,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        time.sleep(wait)
                        continue
                    return {
                        "error": f"arXiv API rate-limited (HTTP {response.status_code}) after retries",
                        "papers": [],
                        "total": 0,
                    }

                response.raise_for_status()
                result = _parse_response(response.text)

                if self.use_cache and self.cache and "error" not in result:
                    self.cache.set(cache_key, cache_params, result)

                return result

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = _retry_wait_seconds(attempt)
                    logger.warning("Request error — waiting %.1fs (retry %d/%d)", wait, attempt + 1, MAX_RETRIES)
                    time.sleep(wait)
                    continue
                return {"error": str(e), "papers": [], "total": 0}

        return {"error": str(last_error) if last_error else "max retries exceeded", "papers": [], "total": 0}
