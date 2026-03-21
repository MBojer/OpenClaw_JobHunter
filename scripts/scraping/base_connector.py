"""
scripts/scraping/base_connector.py
Abstract base class for all job board connectors.
Every board must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobListing:
    """Standardised job record returned by every connector."""
    url:             str                      # Canonical job URL — used as unique key
    title:           str
    company:         str        = ""
    location:        str        = ""
    remote:          bool|None  = None
    salary_raw:      str        = ""          # As-scraped, unparsed
    description_raw: str        = ""          # Full text — Qwen only, never agent
    external_id:     str        = ""          # Board's own ID if available
    scraped_at:      datetime   = field(default_factory=datetime.utcnow)


class BaseConnector(ABC):
    """
    All board connectors extend this class.
    The only method scraping scripts call externally is `fetch()`.
    """

    def __init__(self, config: dict):
        """
        config: dict from board_registry.json for this board.
        Subclasses may read additional keys they need.
        """
        self.config = config

    @abstractmethod
    def fetch(self, queries: list[str]) -> list[JobListing]:
        """
        Fetch job listings for the given search queries.
        Must return a list of JobListing objects.
        Must NOT raise — catch all exceptions internally and return
        whatever was collected before the error.
        """
        ...

    def name(self) -> str:
        return self.config.get("name", self.__class__.__name__)
