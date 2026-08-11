"""Modelos de resultado del diff engine."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from src.models.schema import AntecedenteItem


class NivelMatch(str, Enum):
    EXACTO = "exacto"  # DOI o ISBN en común
    ESTRUCTURADO = "estructurado"  # título normalizado + año en común
    FUZZY = "fuzzy"  # distancia de Levenshtein sobre título normalizado
    SEMANTICO_LLM = "semantico_llm"  # reservado; ver src/matching/llm_semantic.py


class ParEmparejado(BaseModel):
    item_a: AntecedenteItem
    item_b: AntecedenteItem
    nivel: NivelMatch
    score: float | None = None  # similitud 0-100, sólo para nivel FUZZY


class ResultadoDiff(BaseModel):
    pares: list[ParEmparejado]
    solo_en_a: list[AntecedenteItem]
    solo_en_b: list[AntecedenteItem]
