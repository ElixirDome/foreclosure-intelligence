from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SourceDocument:
    source_name: str
    source_url: str
    document_type: str
    content: bytes | str


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