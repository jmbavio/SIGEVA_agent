"""Gancho para razonamiento semántico con LLM sobre candidatos ambiguos que
no matchearon por exact/structured/fuzzy — ej. "Artículos en Revistas" vs
"Publicaciones Periódicas" con títulos parecidos pero no lo bastante
cercanos para el umbral de fuzzy match.

Sólo la interfaz: todavía no hay implementación conectada al motor de
matching (ver `NivelMatch.SEMANTICO_LLM`, que hoy no lo emite nadie)."""
from __future__ import annotations

from typing import Protocol

from src.models.schema import AntecedenteItem


class ResolutorSemanticoLLM(Protocol):
    def resolver(
        self, item: AntecedenteItem, candidatos: list[AntecedenteItem]
    ) -> AntecedenteItem | None:
        """Dado un ítem sin match y una lista acotada de candidatos posibles
        (ej. mismo año, rubro homologado compatible), devuelve el candidato
        que el LLM considera el mismo antecedente, o None si ninguno lo es."""
        ...
