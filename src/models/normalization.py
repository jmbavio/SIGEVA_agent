"""Utilidades de normalización de texto compartidas por models y matching."""
import re
import unicodedata


def normalizar_titulo(titulo: str) -> str:
    """Normaliza un título para comparación: minúsculas, sin tildes, sin
    puntuación, espacios colapsados. Usado tanto por AntecedenteItem
    (campo computado) como por el motor de matching (nivel structured)."""
    if not titulo:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    minusculas = sin_tildes.lower()
    sin_puntuacion = re.sub(r"[^\w\s]", " ", minusculas)
    return re.sub(r"\s+", " ", sin_puntuacion).strip()
