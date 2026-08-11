"""Estado compartido del grafo de diff."""
from __future__ import annotations

from typing import TypedDict

from src.matching.resultado import ResultadoDiff
from src.models.schema import AntecedenteItem


class DiffState(TypedDict, total=False):
    ruta_a: str
    ruta_b: str
    items_a: list[AntecedenteItem]
    items_b: list[AntecedenteItem]
    resultado: ResultadoDiff
    reporte_md: str
