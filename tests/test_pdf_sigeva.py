"""Tests del parser de PDF de SIGEVA sobre texto ya extraído (fabricado acá,
no un PDF real — evita depender de datos personales de nadie). Las mismas
funciones fueron validadas manualmente contra tres exports reales (UNS,
CIC, CONICET) antes de escribir estos tests; ver docstring de
pdf_sigeva.py."""
from src.extractors.pdf_sigeva import (
    _dividir_por_ancla,
    _extraer_bloque_seccion,
    _extraer_campos_por_etiquetas,
    _parsear_articulos,
    _parsear_becarios,
    _parsear_becas_recibidas,
    _parsear_bloque_simple,
    _parsear_cargos_docencia,
    _parsear_cargos_gestion,
    _parsear_categorizacion,
    _parsear_docencia_simple,
    _parsear_eventos,
    _parsear_evaluacion_proyectos,
    _parsear_evaluacion_revistas,
    _parsear_extension,
    _parsear_formacion_academica,
    _parsear_idiomas,
    _parsear_participacion_eventos,
    _parsear_proyectos,
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


def test_parsear_cargos_docencia_con_etiquetas_completas():
    bloque = (
        "Fecha inicio: 08-2024 Hasta: Institución: UNIVERSIDAD DE EJEMPLO Cargo: Profesor adjunto "
        "Tipo de honorarios: Rentado Dedicación: Exclusiva Dedicación horaria semanal: 40 horas o más "
        "Condición: Regular o por concurso Nivel educativo: Universitario de grado "
        "Actividades curriculares: Actividad Profesor responsable Cátedra de Ejemplo Juan Pérez "
        "Fecha inicio: 03-2018 Hasta: 03-2020 Institución: OTRA UNIVERSIDAD Cargo: Profesor titular "
        "Tipo de honorarios: Rentado Dedicación: Simple Dedicación horaria semanal: De 0 hasta 19 horas "
        "Condición: Por contrato Nivel educativo: Universitario de grado "
        "Actividades curriculares: Actividad Profesor responsable Otra Cátedra Ana Gómez"
    )
    registros = _parsear_cargos_docencia(bloque)
    assert len(registros) == 2
    assert registros[0]["titulo"] == "Profesor adjunto - UNIVERSIDAD DE EJEMPLO"
    assert registros[0]["anio"] == 2024
    assert registros[0]["hasta"] is None
    assert registros[1]["titulo"] == "Profesor titular - OTRA UNIVERSIDAD"
    assert registros[1]["anio"] == 2018
    assert registros[1]["hasta"] == "03-2020"


def test_parsear_cargos_docencia_con_etiquetas_truncadas_sin_dos_puntos():
    # Caso real observado en un export de CIC: algunas etiquetas del
    # formulario pierden los dos puntos ("Nivel" en vez de "Nivel
    # educativo:", "Actividades" en vez de "Actividades curriculares:").
    bloque = (
        "Fecha inicio: 08-2024 Hasta: Institución: UNIVERSIDAD DE EJEMPLO Cargo: Profesor adjunto "
        "Tipo de honorarios: Rentado Dedicación: Exclusiva Dedicación horaria 40 horas o más "
        "Condición: Regular o por concurso Nivel Universitario de grado "
        "Actividades Actividad Profesor responsable Cátedra de Ejemplo Juan Pérez"
    )
    registros = _parsear_cargos_docencia(bloque)
    assert len(registros) == 1
    assert registros[0]["titulo"] == "Profesor adjunto - UNIVERSIDAD DE EJEMPLO"
    assert registros[0]["nivel_educativo"] == "Universitario de grado"
    assert "Cátedra de Ejemplo" in registros[0]["actividades_curriculares"]


# --- Secciones de formulario genéricas -----------------------------------


def test_dividir_por_ancla_parte_en_registros():
    bloque = "Fecha inicio: A cosas. Fecha inicio: B otras cosas."
    partes = _dividir_por_ancla(bloque, r"Fecha inicio:")
    assert partes == ["Fecha inicio: A cosas.", "Fecha inicio: B otras cosas."]


def test_dividir_por_ancla_sin_coincidencias_devuelve_vacio():
    assert _dividir_por_ancla("texto sin la ancla", r"Fecha inicio:") == []


def test_extraer_campos_por_etiquetas_tolera_orden_variable_y_ausencias():
    texto = "Cargo: Profesor Institución: UNIVERSIDAD DE EJEMPLO"
    campos = {
        "institucion": r"Instituci[oó]n:",
        "cargo": r"Cargo:",
        "inexistente": r"Etiqueta Que No Está:",
    }
    valores = _extraer_campos_por_etiquetas(texto, campos)
    assert valores["cargo"] == "Profesor"
    assert valores["institucion"] == "UNIVERSIDAD DE EJEMPLO"
    assert valores["inexistente"] is None


def test_parsear_formacion_academica_usa_titulo_o_carrera_como_fallback():
    bloque = (
        "Situación del nivel: Completo Fecha inicio: 05-2008 Fecha egreso: 06-2014 "
        "Denominación de la carrera: Doctorado en Ejemplo Título: Doctor en Ejemplo "
        "Instituciones otorgantes del título: UNIVERSIDAD DE EJEMPLO"
    )
    registros = _parsear_formacion_academica(bloque)
    assert len(registros) == 1
    assert registros[0]["titulo"] == "Doctor en Ejemplo"
    assert registros[0]["anio"] == 2014


def test_parsear_formacion_academica_etiqueta_carrera_truncada_sin_dos_puntos():
    # Caso real de CIC: "Denominación de la" sin "carrera:" ni los dos puntos.
    bloque = "Situación del Completo Fecha inicio: 05-2008 Fecha egreso: 06-2014 Denominación de la Doctorado en Ejemplo Título: Doctor en Ejemplo"
    registros = _parsear_formacion_academica(bloque)
    assert registros[0]["titulo"] == "Doctor en Ejemplo"


def test_parsear_docencia_simple_arma_titulo_desde_cargo_e_institucion():
    bloque = "Fecha inicio: 09-2007 Hasta: 12-2008 Institución: INSTITUTO DE EJEMPLO Cargo: Profesor de Ejemplo"
    registros = _parsear_docencia_simple(bloque)
    assert registros[0]["titulo"] == "Profesor de Ejemplo - INSTITUTO DE EJEMPLO"
    assert registros[0]["anio"] == 2007


def test_parsear_cargos_gestion_con_cargo_inline():
    # Variante real de CONICET: "Cargo:" con valor justo al lado.
    bloque = (
        "Fecha inicio: 01/02/2011 Fin: 01/02/2013 Cargo: Consejero Departamental "
        "Dedicación horaria semanal: De 0 hasta 19 horas "
        "Tipo de función desempeñada: Administrativa Institución: UNIVERSIDAD DE EJEMPLO"
    )
    registros = _parsear_cargos_gestion(bloque)
    assert len(registros) == 1
    assert registros[0]["titulo"] == "Consejero Departamental - UNIVERSIDAD DE EJEMPLO"
    assert registros[0]["anio"] == 2011


def test_parsear_cargos_gestion_con_cargo_flotante():
    # Variante real de UNS: "Cargo:" sin valor, el nombre real aparece
    # como texto libre después de "Dedicación horaria semanal: <valor>".
    bloque = (
        "Fecha inicio: 01/02/2013 Fin: Cargo: Dedicación horaria semanal: De 0 hasta 19 horas "
        "Consejero Departamental Tipo de función desempeñada: De coordinación "
        "Institución: UNIVERSIDAD DE EJEMPLO"
    )
    registros = _parsear_cargos_gestion(bloque)
    assert len(registros) == 1
    assert registros[0]["titulo"] == "Consejero Departamental - UNIVERSIDAD DE EJEMPLO"


def test_parsear_categorizacion_etiqueta_truncada():
    # Caso real de CIC: "Año de" sin "categorización:".
    bloque = (
        "Fecha inicio: 10-2016 Hasta: Año de 2014 "
        "Categoría en el Programa de Incentivos: Categoría IV Institución: UNIVERSIDAD DE EJEMPLO"
    )
    registros = _parsear_categorizacion(bloque)
    assert registros[0]["titulo"] == "Categoría IV - UNIVERSIDAD DE EJEMPLO"
    assert registros[0]["anio"] == 2014


def test_parsear_becarios_arma_titulo_con_nombre_y_apellido():
    bloque = (
        "Año desde: 2026 Año hasta: 2027 Nombre/s: Agustina Apellido/s: Casco Alberino "
        "Institución de trabajo del becario: UNIVERSIDAD DE EJEMPLO Tipo de beca: Iniciación a la Investigación"
    )
    registros = _parsear_becarios(bloque)
    assert registros[0]["titulo"] == "Dirección de becario/a: Agustina Casco Alberino"
    assert registros[0]["anio"] == 2026


def test_parsear_proyectos_usa_denominacion_como_titulo():
    bloque = (
        "Tipo de actividad de Investigación básica Denominación del proyecto: Proyecto de Ejemplo "
        "Fecha desde: 01-2024 Fecha hasta: 12-2027 Descripción del proyecto: Una descripción larga."
    )
    registros = _parsear_proyectos(bloque)
    assert registros[0]["titulo"] == "Proyecto de Ejemplo"
    assert registros[0]["anio"] == 2024


def test_parsear_becas_recibidas_usa_denominacion_o_tipo_de_beca():
    bloque = "Fecha inicio: 04-2015 Fin: 03-2017 Típo de beca: Posdoctorado Denominación de la beca: Beca de Ejemplo"
    registros = _parsear_becas_recibidas(bloque)
    assert registros[0]["titulo"] == "Beca de Ejemplo"
    assert registros[0]["anio"] == 2015


def test_parsear_extension_usa_campo_titulo():
    bloque = "Titulo: Semana de la Ciencia Fecha inicio: 10-2016 Hasta: Función desempeñada: Organizador"
    registros = _parsear_extension(bloque)
    assert registros[0]["titulo"] == "Semana de la Ciencia"
    assert registros[0]["anio"] == 2016


def test_parsear_evaluacion_proyectos():
    bloque = (
        "Año inicio: 2015 Año fin: 2015 Tipos de programas/proyecto evaluados: Proyectos de investigación básica "
        "Institución convocante: MINISTERIO DE EJEMPLO"
    )
    registros = _parsear_evaluacion_proyectos(bloque)
    assert registros[0]["titulo"] == "Proyectos de investigación básica"
    assert registros[0]["anio"] == 2015


def test_parsear_evaluacion_revistas_con_las_dos_etiquetas_posibles():
    # UNS/CIC usan "Título de la revista:"; CONICET usa "Revista seleccionada:".
    bloque_uns = "Título de la revista: Revista de Ejemplo ISSN: Pais: Argentina Año inicio: 2023 Año fin: 2025"
    bloque_conicet = "Revista seleccionada:Revista de Ejemplo Año inicio: 2023 Año fin: 2025 Pais: Argentina"
    for bloque in (bloque_uns, bloque_conicet):
        registros = _parsear_evaluacion_revistas(bloque)
        assert registros[0]["titulo"] == "Revista de Ejemplo"
        assert registros[0]["anio"] == 2023


def test_parsear_participacion_eventos():
    bloque = (
        "Nombre del evento: Congreso de Ejemplo Tipo de evento: Congreso Alcance geográfico: Nacional "
        "Año: 2013 Modo de participación: Asistente Institución organizadora: ASOCIACIÓN DE EJEMPLO"
    )
    registros = _parsear_participacion_eventos(bloque)
    assert registros[0]["titulo"] == "Congreso de Ejemplo"
    assert registros[0]["anio"] == 2013


def test_parsear_idiomas():
    bloque = "Idioma: Inglés Nivel de dominio del idioma: Avanzado Certificado/s obtenido/s: First Certificate in English Año de obtención del certificado: 2000"
    registros = _parsear_idiomas(bloque)
    assert registros[0]["titulo"] == "Inglés (Avanzado)"
    assert registros[0]["anio"] == 2000
