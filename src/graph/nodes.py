"""Nodos del grafo de diff.

`load_instance_a`/`load_instance_b` eligen el extractor según la extensión
del archivo apuntado en el estado: `.pdf` usa el parser genérico de CV
SIGEVA (sirve para cualquier instancia); `.json` usa el extractor de
ejemplo específico de esa instancia (hoy sólo hay para UNS/CONICET, son los
datos de demo versionados en el repo — ver data/README.md)."""
from __future__ import annotations

from pathlib import Path

from src.extractors.conicet import CONICETJSONExtractor
from src.extractors.pdf_sigeva import SIGEVAPdfExtractor
from src.extractors.uns import UNSJSONExtractor
from src.graph.state import DiffState
from src.matching.engine import emparejar
from src.models.schema import InstanciaSigeva
from src.reports.reporte import generar_reporte_markdown

_EXTRACTORES_JSON = {
    InstanciaSigeva.UNS: UNSJSONExtractor,
    InstanciaSigeva.CONICET: CONICETJSONExtractor,
}


def _elegir_extractor(ruta: Path, instancia: InstanciaSigeva):
    if ruta.suffix.lower() == ".pdf":
        return SIGEVAPdfExtractor(instancia)
    extractor_cls = _EXTRACTORES_JSON.get(instancia)
    if extractor_cls is None:
        raise ValueError(
            f"No hay extractor JSON de ejemplo para {instancia.value}; para esa instancia usá un archivo .pdf"
        )
    return extractor_cls()


def load_instance_a(state: DiffState) -> DiffState:
    ruta = Path(state["ruta_a"])
    items = _elegir_extractor(ruta, state["instancia_a"]).extraer(ruta)
    return {"items_a": items}


def load_instance_b(state: DiffState) -> DiffState:
    ruta = Path(state["ruta_b"])
    items = _elegir_extractor(ruta, state["instancia_b"]).extraer(ruta)
    return {"items_b": items}


def normalize(state: DiffState) -> DiffState:
    # Los extractores ya devuelven AntecedenteItem (esquema homologado con
    # título normalizado y clave exacta calculados). Este nodo queda como
    # punto de extensión si a futuro hace falta normalización adicional
    # entre la carga y el matching.
    return {}


def match(state: DiffState) -> DiffState:
    resultado = emparejar(state["items_a"], state["items_b"])
    return {"resultado": resultado}


def report(state: DiffState) -> DiffState:
    reporte_md = generar_reporte_markdown(state["resultado"], state["instancia_a"], state["instancia_b"])
    return {"reporte_md": reporte_md}
