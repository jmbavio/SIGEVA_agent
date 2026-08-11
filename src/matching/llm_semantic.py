"""Razonamiento semántico con LLM sobre candidatos ambiguos que no
matchearon por exact/structured/fuzzy — ej. un antecedente redactado de
forma muy distinta entre plataformas, o clasificado bajo un rubro distinto
(como el caso real de un trabajo marcado "publicado" en una instancia y "no
publicado" en otra, visto en `src/matching/engine.py`).

`ResolutorSemanticoLLM` es la interfaz; `ResolutorSemanticoLangChain` es la
implementación concreta que usa el modelo elegido en `llm_provider.py`
(OpenAI o Gemini según `LLM_PROVIDER`). Se invoca desde
`src/matching/engine.py:resolver_semanticamente`, que es un paso opcional
*posterior* a `emparejar()` — nunca reemplaza los 3 niveles gratuitos, sólo
revisa lo que quedó sin resolver."""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from src.matching.llm_provider import get_chat_model
from src.models.schema import AntecedenteItem


class ResolutorSemanticoLLM(Protocol):
    def resolver(
        self, item: AntecedenteItem, candidatos: list[AntecedenteItem]
    ) -> AntecedenteItem | None:
        """Dado un ítem sin match y una lista acotada de candidatos posibles
        (ej. mismo año, rubro homologado compatible), devuelve el candidato
        que el LLM considera el mismo antecedente, o None si ninguno lo es."""
        ...


class DecisionSemantica(BaseModel):
    es_mismo_antecedente: bool
    indice_candidato: int | None = Field(
        default=None, description="Índice (desde 0) del candidato elegido, si es_mismo_antecedente es true"
    )
    justificacion: str = Field(description="Explicación breve de la decisión, en español")


_PROMPT_SISTEMA = """Ayudás a auditar antecedentes académicos que un mismo investigador cargó \
por separado en distintas instancias de SIGEVA (CONICET, UNS, CIC, CVar). \
Te paso UN antecedente sin match automático (ya se probó exact match por \
DOI/ISBN, match por título normalizado + año, y similitud textual — \
ninguno alcanzó) y una lista de candidatos de la otra plataforma con el \
mismo año o uno cercano.

Decidí si alguno de los candidatos es en realidad EL MISMO antecedente que \
el original, aunque:
- esté redactado distinto (reformulado, orden de palabras distinto, \
  traducido, con o sin subtítulo),
- esté clasificado bajo un rubro distinto entre plataformas (ej. \
  "publicado" en una y "no publicado" en otra, o "artículo" vs "trabajo en \
  evento" si en el fondo es la misma producción).

NO lo consideres el mismo si son dos cosas genuinamente distintas — por \
ejemplo, dos contratos de asesoramiento separados que comparten título \
genérico y año, o dos cátedras distintas dictadas el mismo año."""


def _describir_item(item: AntecedenteItem, indice: int | None = None) -> str:
    encabezado = f"[{indice}] " if indice is not None else ""
    autores = ", ".join(item.autores) if item.autores else "(sin autores registrados)"
    return (
        f"{encabezado}Rubro: {item.rubro.value} (etiqueta original: {item.rubro_original!r})\n"
        f"    Título: {item.titulo!r}\n"
        f"    Año: {item.anio}\n"
        f"    Autores: {autores}"
    )


def _armar_prompt_usuario(item: AntecedenteItem, candidatos: list[AntecedenteItem]) -> str:
    candidatos_texto = "\n".join(_describir_item(c, i) for i, c in enumerate(candidatos))
    return (
        f"Antecedente sin match, de la instancia {item.instancia_origen.value}:\n"
        f"{_describir_item(item)}\n\n"
        f"Candidatos de la otra instancia (mismo año o cercano):\n"
        f"{candidatos_texto}\n\n"
        f"¿Alguno de estos candidatos es el mismo antecedente? Si es así, indicá su índice."
    )


class ResolutorSemanticoLangChain:
    """Implementación de ResolutorSemanticoLLM sobre LangChain, usando el
    modelo que devuelva `get_chat_model()` (OpenAI o Gemini según
    LLM_PROVIDER)."""

    def __init__(self, modelo=None):
        self._modelo = modelo if modelo is not None else get_chat_model()
        self._modelo_estructurado = self._modelo.with_structured_output(DecisionSemantica)

    def resolver(self, item: AntecedenteItem, candidatos: list[AntecedenteItem]) -> AntecedenteItem | None:
        if not candidatos:
            return None

        decision = self._modelo_estructurado.invoke(
            [
                ("system", _PROMPT_SISTEMA),
                ("human", _armar_prompt_usuario(item, candidatos)),
            ]
        )

        if not decision.es_mismo_antecedente or decision.indice_candidato is None:
            return None
        if not 0 <= decision.indice_candidato < len(candidatos):
            return None
        return candidatos[decision.indice_candidato]
