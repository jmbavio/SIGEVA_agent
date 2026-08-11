"""Nodos del grafo de diff. `load_instance_a`/`load_instance_b` están
atados a UNS/CONICET porque son las dos instancias para las que hay
extractor y datos de ejemplo hoy — al sumar CIC/CVar esto se generaliza a
partir de un parámetro de instancia en el estado en lugar de nodos fijos."""
from __future__ import annotations

from pathlib import Path

from src.extractors.conicet import CONICETJSONExtractor
from src.extractors.uns import UNSJSONExtractor
from src.graph.state import DiffState
from src.matching.engine import emparejar
from src.models.schema import InstanciaSigeva
from src.reports.reporte import generar_reporte_markdown


def load_instance_a(state: DiffState) -> DiffState:
    items = UNSJSONExtractor().extraer(Path(state["ruta_a"]))
    return {"items_a": items}


def load_instance_b(state: DiffState) -> DiffState:
    items = CONICETJSONExtractor().extraer(Path(state["ruta_b"]))
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
    reporte_md = generar_reporte_markdown(state["resultado"], InstanciaSigeva.UNS, InstanciaSigeva.CONICET)
    return {"reporte_md": reporte_md}
