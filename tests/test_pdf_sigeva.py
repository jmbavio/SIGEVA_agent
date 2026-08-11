"""Tests del parser de PDF de SIGEVA sobre texto ya extraído (fabricado acá,
no un PDF real — evita depender de datos personales de nadie). Las mismas
funciones fueron validadas manualmente contra dos exports reales (UNS y
CIC) antes de escribir estos tests; ver docstring de pdf_sigeva.py."""
from src.extractors.pdf_sigeva import (
    _extraer_bloque_seccion,
    _parsear_articulos,
    _parsear_bloque_simple,
    _parsear_eventos,
    _parsear_servicios,
    ENCABEZADOS_SECCION,
)


def test_extraer_bloque_seccion_recorta_hasta_el_siguiente_encabezado():
    texto = (
        "PUBLICACIONES - Artículos publicados en revistas: contenido del bloque "
        "de artículos. SERVICIOS: contenido de servicios."
    )
    bloque = _extraer_bloque_seccion(texto, "PUBLICACIONES - Artículos publicados en revistas:")
    assert bloque == "contenido del bloque de artículos."


def test_extraer_bloque_seccion_ausente_devuelve_none():
    assert _extraer_bloque_seccion("texto sin la sección buscada", "SERVICIOS:") is None


def test_encabezados_seccion_incluye_los_usados_por_los_parsers():
    for encabezado in [
        "PUBLICACIONES - Artículos publicados en revistas:",
        "PUBLICACIONES - Trabajos en eventos c-t publicados:",
        "SERVICIOS:",
    ]:
        assert encabezado in ENCABEZADOS_SECCION


def test_parsear_articulos_separa_autores_titulo_revista_y_editorial():
    bloque = (
        "PÉREZ, ANA; GÓMEZ, LUIS. Un título de ejemplo sobre estadística aplicada. "
        "Revista de Ejemplo.: Editorial Ejemplo. 2022 vol.10 n°2. p10 - 20. "
        "issn 1234-5678. eissn 8765-4321"
    )
    registros = _parsear_articulos(bloque)
    assert len(registros) == 1
    r = registros[0]
    assert r["autores"] == "PÉREZ, ANA; GÓMEZ, LUIS"
    assert r["titulo"] == "Un título de ejemplo sobre estadística aplicada"
    assert r["revista"] == "Revista de Ejemplo"
    assert r["editorial"] == "Editorial Ejemplo"
    assert r["anio"] == 2022


def test_parsear_articulos_multiples_registros():
    bloque = (
        "AUTOR, UNO. Primer título. Revista Uno.: Editorial Uno. 2020 vol.1 n°1. p1 - 5. issn 1111-1111\n"
        "AUTOR, DOS. Segundo título. Revista Dos.: Editorial Dos. 2021 vol.2 n°2. p6 - 10. issn 2222-2222"
    )
    registros = _parsear_articulos(bloque)
    assert [r["anio"] for r in registros] == [2020, 2021]
    assert [r["titulo"] for r in registros] == ["Primer título", "Segundo título"]


def test_parsear_articulos_revista_con_ciudad_sin_espacio():
    # Caso real observado: "Revista.Ciudad: Editorial" sin espacio tras el primer punto.
    bloque = (
        "AUTOR, UNO. Un título cualquiera. Revista de Ejemplo.Buenos Aires: Editorial. "
        "2019 vol.3 n°1. p1 - 2. issn 1111-1111."
    )
    registros = _parsear_articulos(bloque)
    assert registros[0]["titulo"] == "Un título cualquiera"
    assert registros[0]["editorial"] == "Editorial"


def test_parsear_eventos_separa_registros_por_pais_ciudad_anio():
    # El título se separa bien incluso con varios registros seguidos; el
    # autor NO se intenta separar acá (ver docstring de _parsear_eventos) —
    # cuando la cola del registro anterior no termina en punto antes del
    # próximo autor (caso real y también el de este fixture), no hay forma
    # confiable de encontrar ese límite con regex solo.
    bloque = (
        "AUTOR UNO; AUTOR DOS. Primer trabajo presentado. Argentina. Buenos Aires. 2019. "
        "Revista. Resumen. Congreso. Congreso Ejemplo. Institución Organizadora "
        "AUTOR TRES. Segundo trabajo presentado. Argentina. Córdoba. 2021. "
        "Revista. Artículo Breve. Congreso. Otro Congreso. Otra Institución"
    )
    registros = _parsear_eventos(bloque)
    assert len(registros) == 2
    assert registros[0]["titulo"] == "Primer trabajo presentado"
    assert registros[0]["anio"] == 2019
    assert registros[1]["titulo"] == "Segundo trabajo presentado"
    assert registros[1]["anio"] == 2021
    assert registros[0]["autores"] is None and registros[1]["autores"] is None


def test_parsear_servicios_separa_registros_por_marcador_y_fechas():
    bloque = (
        "AUTOR UNO. Servicio eventual. Primer servicio de ejemplo. 2020-01-01 - 2020-06-01. "
        "Asesoramientos. Descripción. Rol. Pesos 100.00. Campo. "
        "AUTOR DOS; AUTOR TRES. Servicio eventual. Segundo servicio de ejemplo. 2021-01-01 - 2021-06-01. "
        "Asesoramientos. Descripción. Rol. Pesos 200.00. Campo."
    )
    registros = _parsear_servicios(bloque)
    assert len(registros) == 2
    assert registros[0]["autores"] == "AUTOR UNO"
    assert registros[0]["titulo"] == "Primer servicio de ejemplo"
    assert registros[0]["anio"] == 2020
    assert registros[1]["autores"] == "AUTOR DOS; AUTOR TRES"
    assert registros[1]["titulo"] == "Segundo servicio de ejemplo"
    assert registros[1]["anio"] == 2021


def test_parsear_bloque_simple_extrae_el_ultimo_anio_mencionado():
    bloque = "Universitario de posgrado/doctorado. Un título de tesis. Doctor en Ejemplo. Institución. 2018. Español"
    registros = _parsear_bloque_simple(bloque)
    assert len(registros) == 1
    assert registros[0]["anio"] == 2018


def test_parsear_bloque_simple_vacio_no_genera_registros():
    assert _parsear_bloque_simple("") == []
    assert _parsear_bloque_simple(None) == []
