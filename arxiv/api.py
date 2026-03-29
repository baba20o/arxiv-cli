"""arXiv API client.

Placeholder — will be wired to the real arXiv API.
"""

import logging

logger = logging.getLogger(__name__)


class ArxivClient:
    """Client for the arXiv API."""

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        logger.info("ArxivClient initialized (cache=%s)", use_cache)
