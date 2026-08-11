"""Generación del reporte de diferencias en Markdown a partir de un
ResultadoDiff."""
from __future__ import annotations

from src.matching.resultado import NivelMatch, ResultadoDiff
from src.models.schema import InstanciaSigeva

_ETIQUETA_NIVEL = {
    NivelMatch.EXACTO: "Exacto (DOI/ISBN)",
    NivelMatch.ESTRUCTURADO: "Estructurado (título + año)",
    NivelMatch.FUZZY: "Fuzzy (título similar)",
    NivelMatch.SEMANTICO_LLM: "Semántico (LLM)",
}


def generar_reporte_markdown(
    resultado: ResultadoDiff, instancia_a: InstanciaSigeva, instancia_b: InstanciaSigeva
) -> str:
    lineas: list[str] = [
        f"# Reporte de diferencias: {instancia_a.value} vs {instancia_b.value}",
        "",
        f"- Pares emparejados: {len(resultado.pares)}",
        f"- Sólo en {instancia_a.value}: {len(resultado.solo_en_a)}",
        f"- Sólo en {instancia_b.value}: {len(resultado.solo_en_b)}",
        "",
    ]

    if resultado.pares:
        lineas.append("## Antecedentes emparejados")
        lineas.append("")
        for par in resultado.pares:
            detalle_score = f" (score {par.score:.0f})" if par.score is not None else ""
            lineas.append(f"- **[{_ETIQUETA_NIVEL[par.nivel]}]**{detalle_score} {par.item_a.titulo!r} — {par.item_a.anio}")
            if par.nivel != NivelMatch.EXACTO:
                lineas.append(f"  - {instancia_a.value}: {par.item_a.titulo!r} ({par.item_a.rubro_original})")
                lineas.append(f"  - {instancia_b.value}: {par.item_b.titulo!r} ({par.item_b.rubro_original})")
        lineas.append("")

    if resultado.solo_en_a:
        lineas.append(f"## Sólo presentes en {instancia_a.value}")
        lineas.append("")
        for item in resultado.solo_en_a:
            lineas.append(f"- {item.titulo!r} ({item.anio}, {item.rubro_original})")
        lineas.append("")

    if resultado.solo_en_b:
        lineas.append(f"## Sólo presentes en {instancia_b.value}")
        lineas.append("")
        for item in resultado.solo_en_b:
            lineas.append(f"- {item.titulo!r} ({item.anio}, {item.rubro_original})")
        lineas.append("")

    return "\n".join(lineas)
