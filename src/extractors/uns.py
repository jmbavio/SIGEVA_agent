"""Extractor para exports JSON de la instancia SIGEVA de la UNS.

El formato de campo asumido acá (`categoria`, `titulo`, `anio_publicacion`,
...) es una hipótesis de trabajo con datos de ejemplo, no un formato real
confirmado — ver `data/README.md`."""
from __future__ import annotations

import json
from pathlib import Path

from src.models.schema import AntecedenteItem, InstanciaSigeva, RubroTipo

_MAPA_RUBROS: dict[str, RubroTipo] = {
    "artículos en revistas": RubroTipo.ARTICULO,
    "libros": RubroTipo.LIBRO,
    "capítulos de libros": RubroTipo.CAPITULO_LIBRO,
    "docencia": RubroTipo.DOCENCIA,
    "proyectos": RubroTipo.PROYECTO,
}


def _mapear_rubro(categoria: str) -> RubroTipo:
    return _MAPA_RUBROS.get(categoria.strip().lower(), RubroTipo.OTRO)


class UNSJSONExtractor:
    def extraer(self, ruta: Path) -> list[AntecedenteItem]:
        registros = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return [self._a_antecedente(r) for r in registros]

    def _a_antecedente(self, r: dict) -> AntecedenteItem:
        return AntecedenteItem(
            instancia_origen=InstanciaSigeva.UNS,
            id_origen=r.get("id"),
            rubro=_mapear_rubro(r["categoria"]),
            rubro_original=r["categoria"],
            titulo=r["titulo"],
            anio=r.get("anio_publicacion"),
            doi=r.get("doi"),
            isbn=r.get("isbn"),
            autores=r.get("autores") or [],
            revista_o_editorial=r.get("revista"),
            raw=r,
        )
