"""Punto de entrada del grafo de diff.

Por defecto corre sobre los datos de ejemplo de data/ (JSON ficticio, UNS
vs CONICET). Para correrlo contra tus propios PDFs de SIGEVA (que NUNCA se
versionan — ver .gitignore), seteá estas variables de entorno o en tu .env:

    SIGEVA_RUTA_A=/ruta/local/a/tu_cv_uns.pdf
    SIGEVA_INSTANCIA_A=UNS
    SIGEVA_RUTA_B=/ruta/local/a/tu_cv_conicet.pdf
    SIGEVA_INSTANCIA_B=CONICET

Instancias válidas: UNS, CONICET, CIC, CVAR (ver InstanciaSigeva)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

from src.graph.build import RECURSION_LIMIT, construir_grafo
from src.models.schema import InstanciaSigeva


def main() -> None:
    load_dotenv()

    grafo = construir_grafo()
    estado_inicial = {
        "ruta_a": os.getenv("SIGEVA_RUTA_A", "data/ejemplo_uns.json"),
        "instancia_a": InstanciaSigeva(os.getenv("SIGEVA_INSTANCIA_A", "UNS")),
        "ruta_b": os.getenv("SIGEVA_RUTA_B", "data/ejemplo_conicet.json"),
        "instancia_b": InstanciaSigeva(os.getenv("SIGEVA_INSTANCIA_B", "CONICET")),
    }
    config = {"configurable": {"thread_id": "diff-run-1"}, "recursion_limit": RECURSION_LIMIT}

    estado_final = grafo.invoke(estado_inicial, config=config)
    print(estado_final["reporte_md"])


if __name__ == "__main__":
    main()
