"""Diff engine de tres niveles: exact match (DOI/ISBN) → structured match
(título normalizado + año) → fuzzy match (Levenshtein sobre título
normalizado, umbral configurable).

Los candidatos que no matchean en ninguno de los tres niveles quedan en
`solo_en_a` / `solo_en_b` de `ResultadoDiff`. `resolver_semanticamente` es
una cuarta pasada *opcional*, posterior y separada de `emparejar` (no
consume API ni cuesta nada si no se llama): le pasa esos sobrantes al
resolutor LLM de `llm_semantic.py`."""
from __future__ import annotations

from collections.abc import Callable

from rapidfuzz import fuzz

from src.matching.llm_semantic import ResolutorSemanticoLLM
from src.matching.resultado import NivelMatch, ParEmparejado, ResultadoDiff
from src.models.schema import AntecedenteItem

UMBRAL_FUZZY_DEFAULT = 85.0
UMBRAL_ANIO_SEMANTICO_DEFAULT = 1
MAX_CANDIDATOS_SEMANTICO_DEFAULT = 5


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


def _candidatos_probables(
    item: AntecedenteItem,
    pendientes: list[AntecedenteItem],
    umbral_anio: int,
    max_candidatos: int,
) -> list[AntecedenteItem]:
    """Candidatos con año igual o cercano, priorizados por similitud de
    título (aunque estén debajo del umbral fuzzy) para acotar cuántos se le
    mandan al LLM por llamada."""
    if item.anio is None:
        return []
    cercanos = [c for c in pendientes if c.anio is not None and abs(c.anio - item.anio) <= umbral_anio]
    cercanos.sort(key=lambda c: fuzz.ratio(item.titulo_normalizado, c.titulo_normalizado), reverse=True)
    return cercanos[:max_candidatos]


def resolver_semanticamente(
    resultado: ResultadoDiff,
    resolutor: ResolutorSemanticoLLM,
    umbral_anio: int = UMBRAL_ANIO_SEMANTICO_DEFAULT,
    max_candidatos: int = MAX_CANDIDATOS_SEMANTICO_DEFAULT,
) -> ResultadoDiff:
    """Pasa lo que quedó en `solo_en_a`/`solo_en_b` de un ResultadoDiff por
    el resolutor LLM, una llamada por ítem de `solo_en_a` con candidatos
    cercanos en año. No modifica `resultado`; devuelve uno nuevo."""
    pendientes_b = list(resultado.solo_en_b)
    pares = list(resultado.pares)
    aun_sin_a: list[AntecedenteItem] = []

    for item_a in resultado.solo_en_a:
        candidatos = _candidatos_probables(item_a, pendientes_b, umbral_anio, max_candidatos)
        elegido = resolutor.resolver(item_a, candidatos) if candidatos else None
        if elegido is not None:
            pendientes_b.remove(elegido)
            pares.append(ParEmparejado(item_a=item_a, item_b=elegido, nivel=NivelMatch.SEMANTICO_LLM))
        else:
            aun_sin_a.append(item_a)

    return ResultadoDiff(pares=pares, solo_en_a=aun_sin_a, solo_en_b=pendientes_b)
