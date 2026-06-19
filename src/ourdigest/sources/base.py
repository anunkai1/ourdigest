"""Source interface — every concrete source implements fetch()."""
from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from ..models import Story


class Source(ABC):
    """A pull-based feed of Story objects. Implementations are stateless."""

    source_type: str = "abstract"

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    async def fetch(
        self,
        client: httpx.AsyncClient,
        *,
        lookback_hours: int,
        limit: int,
    ) -> list[Story]:
        """Return up to ``limit`` stories newer than ``lookback_hours`` ago."""

    def _label(self) -> str:
        return self.name
