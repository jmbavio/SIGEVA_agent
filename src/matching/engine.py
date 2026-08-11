"""Diff engine de tres niveles: exact match (DOI/ISBN) → structured match
(título normalizado + año) → fuzzy match (Levenshtein sobre título
normalizado, umbral configurable).

Los candidatos que no matchean en ninguno de los tres niveles quedan en
`solo_en_a` / `solo_en_b` de `ResultadoDiff` — son los que, a futuro, podría
revisar el resolutor semántico de `llm_semantic.py`."""
from __future__ import annotations

from collections.abc import Callable

from rapidfuzz import fuzz

from src.matching.resultado import NivelMatch, ParEmparejado, ResultadoDiff
from src.models.schema import AntecedenteItem

UMBRAL_FUZZY_DEFAULT = 85.0


def _extraer_primero(candidatos: list[AntecedenteItem], predicado: Callable[[AntecedenteItem], bool]) -> AntecedenteItem | None:
    for i, candidato in enumerate(candidatos):
        if predicado(candidato):
            return candidatos.pop(i)
    return None


def emparejar(
    items_a: list[AntecedenteItem],
    items_b: list[AntecedenteItem],
    umbral_fuzzy: float = UMBRAL_FUZZY_DEFAULT,
) -> ResultadoDiff:
    pendientes_b = list(items_b)
    pares: list[ParEmparejado] = []
    sin_match_a: list[AntecedenteItem] = []

    for item_a in items_a:
        emparejado = None

        if item_a.clave_exacta is not None:
            emparejado = _extraer_primero(pendientes_b, lambda b: b.clave_exacta == item_a.clave_exacta)
            if emparejado is not None:
                pares.append(ParEmparejado(item_a=item_a, item_b=emparejado, nivel=NivelMatch.EXACTO))
                continue

        emparejado = _extraer_primero(
            pendientes_b,
            lambda b: b.titulo_normalizado == item_a.titulo_normalizado and b.anio == item_a.anio,
        )
        if emparejado is not None:
            pares.append(ParEmparejado(item_a=item_a, item_b=emparejado, nivel=NivelMatch.ESTRUCTURADO))
            continue

        sin_match_a.append(item_a)

    aun_sin_a: list[AntecedenteItem] = []
    for item_a in sin_match_a:
        mejor_candidato: AntecedenteItem | None = None
        mejor_score = 0.0
        for candidato in pendientes_b:
            score = fuzz.ratio(item_a.titulo_normalizado, candidato.titulo_normalizado)
            if score > mejor_score:
                mejor_score = score
                mejor_candidato = candidato

        if mejor_candidato is not None and mejor_score >= umbral_fuzzy:
            pendientes_b.remove(mejor_candidato)
            pares.append(
                ParEmparejado(item_a=item_a, item_b=mejor_candidato, nivel=NivelMatch.FUZZY, score=mejor_score)
            )
        else:
            aun_sin_a.append(item_a)

    return ResultadoDiff(pares=pares, solo_en_a=aun_sin_a, solo_en_b=pendientes_b)
