"""Interfaz común para los extractores de cada instancia SIGEVA.

Por ahora todos leen desde exports JSON locales (`data/`). El login y
scraping en vivo contra cada plataforma queda para una etapa posterior."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.models.schema import AntecedenteItem


class InstanciaExtractor(Protocol):
    """Cualquier extractor debe poder tomar una fuente (por ahora, un path a
    JSON) y devolver una lista de AntecedenteItem ya homologados."""

    def extraer(self, ruta: Path) -> list[AntecedenteItem]: ...
