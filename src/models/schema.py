"""Esquema homologado de "ítem de antecedente" — el formato intermedio común
al que se traduce lo extraído de cada instancia SIGEVA (UNS, CONICET, CIC,
CVar) antes de compararlas."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field

from src.models.normalization import normalizar_titulo


class InstanciaSigeva(str, Enum):
    UNS = "UNS"
    CONICET = "CONICET"
    CIC = "CIC"
    CVAR = "CVAR"


class RubroTipo(str, Enum):
    """Categoría homologada del antecedente, basada en la taxonomía del
    "Banco de Datos" de SIGEVA/CONICET (Publicaciones, Formación de RRHH,
    Cargos, Financiamiento CyT, Evaluación, Extensión, Producciones y
    Servicios). `rubro_original` conserva la etiqueta tal cual la usa cada
    instancia (pueden diferir en texto aunque refieran al mismo rubro, ej.
    "Artículos en Revistas" vs "Publicaciones Periódicas")."""

    # Publicaciones
    ARTICULO = "articulo"  # Artículos publicados en revistas
    LIBRO = "libro"
    CAPITULO_LIBRO = "capitulo_libro"  # Partes de libros
    TRABAJO_EVENTO = "trabajo_evento"  # Congresos/ponencias publicados
    TESIS = "tesis"
    INFORME_TECNICO = "informe_tecnico"
    OTRA_PRODUCCION_CT = "otra_produccion_ct"
    TRABAJO_EVENTO_NO_PUBLICADO = "trabajo_evento_no_publicado"

    # Producciones y servicios
    PRODUCCION_ARTISTICA = "produccion_artistica"
    DESARROLLO_TECNOLOGICO = "desarrollo_tecnologico"
    SERVICIO = "servicio"
    PATENTE = "patente"

    # Cargos
    DOCENCIA = "docencia"
    CARGO_ID = "cargo_id"  # Cargos en organismos científico-tecnológicos
    CARGO_GESTION = "cargo_gestion"  # Cargos en gestión institucional

    # Financiamiento CyT
    PROYECTO = "proyecto"  # Proyectos de I+D, extensión, vinculación
    SUBSIDIO = "subsidio"

    # Formación de RRHH en CyT (dirección de becarios/tesistas/investigadores)
    DIRECCION_BECARIO = "direccion_becario"
    DIRECCION_TESIS = "direccion_tesis"
    DIRECCION_INVESTIGADOR = "direccion_investigador"

    # Otros
    EVALUACION = "evaluacion"
    EXTENSION = "extension"
    OTRO = "otro"


class AntecedenteItem(BaseModel):
    """Ítem de antecedente académico en formato intermedio, independiente de
    la instancia SIGEVA de origen."""

    instancia_origen: InstanciaSigeva
    id_origen: str | None = Field(
        default=None, description="ID/PK del registro en la instancia de origen, si la expone"
    )

    rubro: RubroTipo
    rubro_original: str = Field(description="Etiqueta de rubro tal cual figura en la instancia de origen")

    titulo: str
    anio: int | None = None

    doi: str | None = None
    isbn: str | None = None

    autores: list[str] = Field(default_factory=list)
    revista_o_editorial: str | None = None

    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Campos crudos originales tal cual vinieron de la fuente, sin perder info específica de la plataforma",
    )

    extraido_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field  # type: ignore[misc]
    @property
    def titulo_normalizado(self) -> str:
        return normalizar_titulo(self.titulo)

    @computed_field  # type: ignore[misc]
    @property
    def clave_exacta(self) -> str | None:
        """Clave para exact match por DOI o ISBN (en ese orden de prioridad).
        None si el ítem no tiene ninguno de los dos."""
        if self.doi:
            return f"doi:{self.doi.strip().lower()}"
        if self.isbn:
            return f"isbn:{self.isbn.strip().replace('-', '')}"
        return None
