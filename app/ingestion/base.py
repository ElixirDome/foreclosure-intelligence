from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SourceDocument:
    """
    Raw document payload from a source adapter.

    Adapters answer "where do I get the document?" — not how to parse
    every field inside it. Interpretation happens after the document is
    stored and chunked.
    """

    source_name: str
    source_url: str
    document_type: str
    content: bytes | str
    title: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    storage_path: str | None = None


class SourceAdapter(ABC):

    @abstractmethod
    def fetch(self) -> list[Any]:
        """Fetch raw items from the external source."""
        raise NotImplementedError

    @abstractmethod
    def extract(self, item: Any) -> dict:
        """Convert a raw source item into structured property data."""
        raise NotImplementedError

    def get_documents(self, item: Any) -> list[SourceDocument]:
        """Return documents associated with the property."""
        return []