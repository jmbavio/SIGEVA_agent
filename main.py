"""Punto de entrada: corre el grafo de diff sobre los datos de ejemplo de
data/ y muestra el reporte de diferencias en Markdown."""
from __future__ import annotations

from dotenv import load_dotenv

from src.graph.build import RECURSION_LIMIT, construir_grafo


def main() -> None:
    load_dotenv()

    grafo = construir_grafo()
    estado_inicial = {
        "ruta_a": "data/ejemplo_uns.json",
        "ruta_b": "data/ejemplo_conicet.json",
    }
    config = {"configurable": {"thread_id": "diff-run-1"}, "recursion_limit": RECURSION_LIMIT}

    estado_final = grafo.invoke(estado_inicial, config=config)
    print(estado_final["reporte_md"])


if __name__ == "__main__":
    main()
