"""Extractor para exports JSON de la instancia SIGEVA de CONICET.

El formato de campo asumido acá (`rubro`, `titulo_trabajo`, `anio`, ...) es
una hipótesis de trabajo con datos de ejemplo, no un formato real
confirmado — ver `data/README.md`. Las categorías de `_MAPA_RUBROS` sí están
tomadas de la taxonomía real del "Banco de Datos" de SIGEVA/CONICET."""
from __future__ import annotations

import json
from pathlib import Path

from src.models.schema import AntecedenteItem, InstanciaSigeva, RubroTipo

_MAPA_RUBROS: dict[str, RubroTipo] = {
    "artículos publicados en revistas": RubroTipo.ARTICULO,
    "publicaciones periódicas": RubroTipo.ARTICULO,
    "libros": RubroTipo.LIBRO,
    "partes de libros": RubroTipo.CAPITULO_LIBRO,
    "trabajos en eventos c-t publicados": RubroTipo.TRABAJO_EVENTO,
    "tesis": RubroTipo.TESIS,
    "informes técnicos": RubroTipo.INFORME_TECNICO,
    "cargos docentes": RubroTipo.DOCENCIA,
    "cargos en organismos científico-tecnológicos": RubroTipo.CARGO_ID,
    "cargos en gestión institucional": RubroTipo.CARGO_GESTION,
    "proyectos de i+d": RubroTipo.PROYECTO,
    "formación de recursos humanos": RubroTipo.DIRECCION_BECARIO,
}


def _mapear_rubro(rubro: str) -> RubroTipo:
    return _MAPA_RUBROS.get(rubro.strip().lower(), RubroTipo.OTRO)


def _autores_desde_lista(autores_lista: str | None) -> list[str]:
    if not autores_lista:
        return []
    return [a.strip() for a in autores_lista.split(";") if a.strip()]


class CONICETJSONExtractor:
    def extraer(self, ruta: Path) -> list[AntecedenteItem]:
        registros = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return [self._a_antecedente(r) for r in registros]

    def _a_antecedente(self, r: dict) -> AntecedenteItem:
        return AntecedenteItem(
            instancia_origen=InstanciaSigeva.CONICET,
            id_origen=r.get("codigo_interno"),
            rubro=_mapear_rubro(r["rubro"]),
            rubro_original=r["rubro"],
            titulo=r["titulo_trabajo"],
            anio=r.get("anio"),
            doi=r.get("doi"),
            isbn=r.get("isbn"),
            autores=_autores_desde_lista(r.get("autores_lista")),
            revista_o_editorial=r.get("publicacion"),
            raw=r,
        )
