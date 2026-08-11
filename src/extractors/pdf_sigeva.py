"""Extractor genérico para el PDF de "Curriculum vitae" que exportan las
distintas instancias SIGEVA (UNS, CONICET, CIC, CVar).

Validado contra exports reales de tres instancias distintas (UNS, CIC,
CONICET): comparten el mismo layout de secciones letra por letra (mismo
software SIGEVA, distinta marca institucional), así que un solo parser
sirve para todas — sólo cambia `instancia_origen`, que se pasa como
parámetro.

Usa pdfplumber (no pypdf) porque reconstruye el orden de lectura visual.
Esto es imprescindible para las secciones con layout de formulario en dos
columnas (CARGOS, FINANCIAMIENTO CYT, FORMACION DE RRHH): pypdf devuelve
esas etiquetas y valores en el orden del content stream del PDF, que no
coincide con el orden en que se ven en pantalla (mezcla todas las
etiquetas de un lado, después todos los valores del otro).

Cobertura: se parsean TODAS las secciones de antecedentes del CV (todo lo
que no es DATOS PERSONALES/EXPERTICIA EN CYT, que son datos personales sin
equivalente de "antecedente" comparable): Publicaciones (artículos,
trabajos en eventos publicados/no publicados, tesis, demás producciones),
Servicios, Formación académica (posgrado/grado/terciario/posdoctorado),
Formación complementaria (cursos, idiomas), Docencia (nivel superior,
básico/medio, cursos de posgrado), Cargos en gestión institucional,
Categorización del programa de incentivos, Formación de RRHH (becarios),
Financiamiento CyT (proyectos I+D, becas recibidas), Extensión,
Evaluación (programas/proyectos, trabajos en revistas), y Redes/gestión
editorial (participación en eventos).

Dos familias de parser según el formato de la sección:
- **Citas** (artículos, eventos, servicios): un registro es una oración
  con puntuación, se separan con heurísticas de texto sobre el límite
  autor/título (ver `_particionar_por_ultimo_limite` /
  `_particionar_por_primer_limite`).
- **Formularios** (todo lo demás): pares "Etiqueta: Valor". La mayoría usa
  `_extraer_campos_por_etiquetas`, que busca cada etiqueta de forma
  independiente y no depende de que vengan en un orden fijo — importante
  porque el orden y la presencia de etiquetas varía entre instancias (ver
  abajo). CARGOS - Docencia y CARGOS EN GESTION INSTITUCIONAL usan un
  regex encadenado en cambio, porque ahí sí hace falta capturar texto
  libre sin etiqueta propia (ver sus docstrings).

Limitaciones conocidas (ver README):
- El export no incluye DOI en ningún caso observado, y el ISBN tampoco
  aparece en los rubros parseados acá. El nivel de exact match del diff
  engine va a disparar poco con datos de PDF.
- La separación autor/título/revista de artículos se resuelve con
  heurísticas de texto, no con un parser gramatical completo. Un título
  que contenga ". " seguido de mayúscula puede cortarse antes de lo
  debido (ver caso "VALVULOAORTOPATÍA BICÚSPIDE." en el README de datos).
- En "trabajos en eventos" el campo `autores` no se separa de forma
  confiable de la cola del registro anterior — se deja en `None`.
  `titulo` y `anio` sí están validados.
- **Las mismas etiquetas varían entre instancias**, y no siempre por
  truncamiento consistente — encontrado validando contra datos reales:
  - CIC trunca varias etiquetas largas sin los dos puntos ("Nivel" en vez
    de "Nivel educativo:", "Año de" en vez de "Año de categorización:",
    "Título de la" en vez de "Título de la revista:") — y lo hace de
    forma *inconsistente* entre registros del mismo documento (a veces la
    misma etiqueta sale completa, a veces truncada).
  - CONICET usa una etiqueta totalmente distinta para el nombre de la
    revista evaluada ("Revista seleccionada:" en vez de "Título de la
    revista:") — no es truncamiento, es otro texto.
  - El campo "Cargo:" de CARGOS EN GESTION INSTITUCIONAL tiene su valor
    en dos posiciones posibles según la instancia (ver
    `_parsear_cargos_gestion`): UNS lo deja sin valor adyacente y el
    nombre real aparece como texto libre más adelante; CONICET lo pone
    donde se espera.
  Cada uno de estos casos está cubierto con un test específico en
  tests/test_pdf_sigeva.py.
"""
from __future__ import annotations

import html
import re
from collections.abc import Callable
from pathlib import Path

import pdfplumber

from src.models.schema import AntecedenteItem, InstanciaSigeva, RubroTipo

# El nombre de la institución varía por instancia (UNIVERSIDAD NACIONAL DEL
# SUR / COMISION DE INVEST.CIENTIFICAS / CONSEJO NACIONAL...) y además
# puede aparecer como valor legítimo de un campo "Institución:" en CARGOS —
# por eso el encabezado de página NO se filtra por el nombre de la
# institución, sino por posición: todo lo que viene antes de (e incluyendo)
# la línea "Curriculum vitae" / "Currículum vitae APELLIDO, NOMBRE", que sí
# aparece siempre en ese lugar en las 3 instancias validadas.
_CABECERA_PAGINA_RE = re.compile(r"^Curr[íi]culum vitae\b")
# El pie de página si es más regular: siempre menciona "Fecha de
# impresión:" y/o "Página N de M" (a veces en la misma línea, a veces no).
_PIE_PAGINA_RE = re.compile(r"^(Fecha de impresión:.*|(\d{2}/\d{2}/\d{4}\s*)?Página\s+\d+\s+de\s+\d+.*)$")

# Todos los encabezados de sección conocidos del layout SIGEVA, verificados
# letra por letra (incluido el espaciado) contra el texto real extraído con
# pdfplumber de las 3 instancias validadas (UNS, CIC, CONICET). Se usan
# como límites al recortar el bloque de texto de una sección puntual — un
# espaciado que no coincide exactamente hace que ese límite nunca matchee
# (bug real que hubo acá: "FORMACION COMPLEMENTARIA -  Idiomas:" con doble
# espacio, copiado mal de una vista renderizada, nunca encontraba nada).
ENCABEZADOS_SECCION = (
    "DATOS PERSONALES - IDENTIFICACION",
    "DATOS PERSONALES - DIRECCION RESIDENCIAL",
    "DATOS PERSONALES - LUGAR DE TRABAJO",
    "EXPERTICIA EN CYT",
    # Encabezados de grupo sin ":" — no se parsean como sección propia,
    # pero sí sirven de límite para no filtrarse dentro del bloque de la
    # sección anterior (ver bug real: "ANTECEDENTES" quedaba pegado al
    # final de CATEGORIZACION DEL PROGRAMA DE INCENTIVOS).
    "FORMACION",
    "CARGOS",
    "ANTECEDENTES",
    "PRODUCCION",
    "FORMACION ACADEMICA - Nivel Universitario de Posgrado/Doctorado:",
    "FORMACION ACADEMICA - Nivel Universitario de Grado:",
    "FORMACION ACADEMICA - Nivel Terciario no Universitario:",
    "FORMACION COMPLEMENTARIA - Posdoctorado:",
    "FORMACION COMPLEMENTARIA - Cursos de posgrado y/o capacit. extracurriculares:",
    "FORMACION COMPLEMENTARIA - Idiomas:",
    "DOCENCIA - Nivel superior universitario y/o posgrado:",
    "DOCENCIA - Nivel básico/medio:",
    "DOCENCIA - Cursos de posgrado y capacitaciones extracurriculares",
    "CARGOS EN GESTION INSTITUCIONAL:",
    "CATEGORIZACION DEL PROGRAMA DE INCENTIVOS:",
    "FORMACION DE RRHH EN CYT - Becarios:",
    "FINANCIAMIENTO CYT - Proyectos I+D:",
    "FINANCIAMIENTO CYT - Becas recibidas:",
    "EXTENSION - Comunicación pública de la ciencia y la tecnología:",
    "EVALUACION - Evaluación de programas/proyectos de I+D y/o extensión:",
    "EVALUACION - Evaluación de trabajos en revistas CyT:",
    "PUBLICACIONES - Artículos publicados en revistas:",
    "PUBLICACIONES - Trabajos en eventos c-t publicados:",
    "PUBLICACIONES - Tesis:",
    "PUBLICACIONES - Demás producciones c-t publicados:",
    "SERVICIOS:",
    "OTROS ANTECEDENTES",
    "REDES, GESTION EDITORIAL Y EVENTOS - Participación u organización de eventos cyt:",
    "REDES, GESTION EDITORIAL Y EVENTOS - Trabajos en eventos c-t no publicados:",
)

# Límite genérico: punto + espacio seguido de algo que arranca un nuevo
# "campo" de texto libre (mayúscula, dígito, comilla o guión). Usado para
# partir autor/título tomando el ÚLTIMO límite dentro de un tramo de texto
# (así se saltea límites falsos que caen en medio de la cola del registro
# anterior, ej. "Revista. Resumen. Congreso. NombreCongreso. Institución").
_LIMITE_RE = re.compile(r"\.\s+(?=[A-ZÁÉÍÓÚÑ0-9¡¿\"'\-\\])")


def _particionar_por_ultimo_limite(texto: str) -> tuple[str | None, str]:
    """Autor/resto usando el ÚLTIMO límite de la cadena. Sirve cuando texto
    puede contener la cola de un registro anterior antes del autor real
    (ver el docstring de _LIMITE_RE)."""
    limites = list(_LIMITE_RE.finditer(texto))
    if not limites:
        return None, texto.strip()
    corte = limites[-1].end()
    return texto[:corte].rstrip(". ").strip(), texto[corte:].strip()


def _particionar_por_primer_limite(texto: str) -> tuple[str | None, str]:
    """Autor/resto usando el PRIMER límite de la cadena. Sirve cuando texto
    empieza directamente en el autor (sin cola previa de otro registro) y
    puede contener más de un límite después (ej. título y luego revista)."""
    m = _LIMITE_RE.search(texto)
    if not m:
        return None, texto.strip()
    return texto[: m.start() + 1].rstrip(". ").strip(), texto[m.end() :].strip()


_LIGADURAS = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}


def _limpiar_titulo(titulo: str) -> str:
    limpio = html.unescape(titulo)
    for ligadura, expandida in _LIGADURAS.items():
        limpio = limpio.replace(ligadura, expandida)
    return limpio.strip().rstrip(".").strip().strip('"').strip()


def _autores_desde_texto(autores: str | None) -> list[str]:
    if not autores:
        return []
    return [a.strip() for a in autores.split(";") if a.strip()]


def _anio_desde_texto(texto: str | None) -> int | None:
    if not texto:
        return None
    m = re.search(r"(19|20)\d{2}", texto)
    return int(m.group()) if m else None


# --- Utilidades genéricas para secciones con layout de formulario --------
# A diferencia de las secciones de citas (artículos, eventos, servicios),
# estas secciones son pares "Etiqueta: Valor" cuyo orden y presencia varía
# entre sub-secciones y entre instancias (CIC trunca varias etiquetas, a
# veces sin los dos puntos). En vez de encadenar un regex gigante por campo
# fijo (como en CARGOS - Docencia), acá cada campo se busca de forma
# independiente y su valor es "todo lo que sigue hasta la próxima etiqueta
# conocida que aparezca después" — tolera campos ausentes y fuera de orden.
def _dividir_por_ancla(bloque: str, ancla: str) -> list[str]:
    posiciones = [m.start() for m in re.finditer(ancla, bloque)]
    if not posiciones:
        return []
    posiciones.append(len(bloque))
    return [bloque[posiciones[i] : posiciones[i + 1]].strip() for i in range(len(posiciones) - 1)]


def _extraer_campos_por_etiquetas(texto: str, etiquetas: dict[str, str]) -> dict[str, str | None]:
    posiciones = []
    for nombre, patron in etiquetas.items():
        m = re.search(patron, texto)
        if m:
            posiciones.append((m.start(), m.end(), nombre))
    posiciones.sort()
    resultado: dict[str, str | None] = dict.fromkeys(etiquetas)
    for i, (_, fin_etiqueta, nombre) in enumerate(posiciones):
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(texto)
        valor = texto[fin_etiqueta:fin].strip().strip(".").strip()
        resultado[nombre] = valor or None
    return resultado


def _texto_completo(ruta: Path) -> str:
    """pdfplumber (no pypdf) porque reconstruye el orden de lectura visual de
    las secciones con layout de formulario en dos columnas (CARGOS,
    FINANCIAMIENTO CYT, FORMACION DE RRHH) — pypdf devuelve esas etiquetas y
    valores en el orden del content stream del PDF, que no coincide con el
    orden en que se ven en pantalla."""
    lineas: list[str] = []
    with pdfplumber.open(ruta) as pdf:
        for page in pdf.pages:
            texto_pagina = page.extract_text() or ""
            lineas_pagina = [l.strip() for l in texto_pagina.split("\n") if l.strip()]
            lineas.extend(_quitar_cabecera_y_pie(lineas_pagina))
    texto = " ".join(lineas)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _quitar_cabecera_y_pie(lineas_pagina: list[str]) -> list[str]:
    for i, linea in enumerate(lineas_pagina):
        if _CABECERA_PAGINA_RE.match(linea):
            lineas_pagina = lineas_pagina[i + 1 :]
            break
    return [l for l in lineas_pagina if not _PIE_PAGINA_RE.match(l)]


def _extraer_bloque_seccion(texto: str, encabezado: str) -> str | None:
    inicio = texto.find(encabezado)
    if inicio == -1:
        return None
    inicio += len(encabezado)
    fin = len(texto)
    for otro in ENCABEZADOS_SECCION:
        if otro == encabezado:
            continue
        pos = texto.find(otro, inicio)
        if pos != -1:
            fin = min(fin, pos)
    return texto[inicio:fin].strip()


# --- Artículos publicados en revistas ---------------------------------
# Formato: AUTORES. TITULO. REVISTA[.CIUDAD]: EDITORIAL. AÑO vol.N n°N.
#          pP-P. issn X. eissn Y
_COLA_ARTICULO_RE = re.compile(
    r"(?P<anio>\d{4})\s+vol\.(?P<vol>[^\s]*)\s*n[°º](?P<numero>[^\s.]*)\.?\s*"
    r"p(?P<paginas>[^.]*)(?:\.\s*)+"
    r"(?:issn\s+(?P<issn>[\dXx\-]+)\s*(?:\.\s*)+)?"
    r"(?:eissn\s+(?P<eissn>[\dXx\-]+))?\.?"
)


def _parsear_articulos(bloque: str) -> list[dict]:
    registros = []
    pos = 0
    for m in _COLA_ARTICULO_RE.finditer(bloque):
        registros.append((bloque[pos : m.end()].strip(), m.groupdict()))
        pos = m.end()

    resultado = []
    for texto_registro, cola in registros:
        marca_cola = f"{cola['anio']} vol."
        idx_cola = texto_registro.rfind(marca_cola)
        antes_de_cola = texto_registro[:idx_cola] if idx_cola != -1 else texto_registro
        autores, resto = _particionar_por_primer_limite(antes_de_cola)
        idx_dospuntos = resto.rfind(": ")
        if idx_dospuntos == -1:
            titulo, revista, editorial = resto, None, None
        else:
            revista_y_titulo = resto[:idx_dospuntos].rstrip(". ")
            editorial = resto[idx_dospuntos + 2 :].rstrip(". ") or None
            m2 = re.match(r"^(?P<titulo>.+?)\.\s*(?P<revista>[A-ZÁÉÍÓÚÑ0-9].*)$", revista_y_titulo, re.DOTALL)
            if m2:
                titulo, revista = m2.group("titulo"), m2.group("revista")
            else:
                titulo, revista = revista_y_titulo, None
        resultado.append(
            {
                "autores": autores,
                "titulo": _limpiar_titulo(titulo),
                "revista": revista,
                "editorial": editorial,
                "anio": int(cola["anio"]),
                "raw_text": texto_registro,
            }
        )
    return resultado


# --- Trabajos en eventos (publicados y no publicados) ------------------
# Formato: AUTORES. TITULO. PAIS. CIUDAD. AÑO. <cola libre>
#
# A diferencia de artículos y servicios, acá la cola libre (tipo de
# publicación, congreso, institución organizadora) NO siempre termina en un
# punto antes del autor del próximo registro — a veces sólo hay un espacio.
# Eso hace que el límite derecho no alcance para separar el autor de la
# cola del registro anterior: `titulo` queda limpio (validado contra datos
# reales), pero `autores` puede venir con esa cola pegada adelante. No se
# guarda en `autores` para no propagar el dato sucio — queda en `raw_text`.
_ANCLA_EVENTO_RE = re.compile(
    r"(?P<pais>[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]+)*)\.\s*"
    r"(?P<ciudad>[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]+)*)\.\s*"
    r"(?P<anio>\d{4})\.\s*"
)


def _parsear_eventos(bloque: str) -> list[dict]:
    anclas = list(_ANCLA_EVENTO_RE.finditer(bloque))
    resultado = []
    prev_end = 0
    for m in anclas:
        gap = bloque[prev_end : m.start()]
        _, titulo = _particionar_por_ultimo_limite(gap)
        autores = None
        resultado.append(
            {
                "autores": autores,
                "titulo": _limpiar_titulo(titulo),
                "pais": m.group("pais"),
                "anio": int(m.group("anio")),
                "raw_text": bloque[prev_end : m.end()].strip(),
            }
        )
        prev_end = m.end()
    return resultado


# --- Servicios -----------------------------------------------------------
# Formato: AUTORES. Servicio eventual. TITULO. FECHA_DESDE - FECHA_HASTA. ...
_MARCADOR_SERVICIO_RE = re.compile(r"\.\s*Servicio eventual\.\s*")
_FECHA_SERVICIO_RE = re.compile(
    r"(?P<titulo>.+?)\.\s*(?P<fecha_desde>\d{4}-\d{2}-\d{2})\s*-\s*(?P<fecha_hasta>\d{4}-\d{2}-\d{2})\.\s*",
    re.DOTALL,
)


def _parsear_servicios(bloque: str) -> list[dict]:
    marcadores = list(_MARCADOR_SERVICIO_RE.finditer(bloque))
    resultado = []
    prev_end = 0
    for m in marcadores:
        # El autor del registro actual es el ÚLTIMO tramo del gap (todo lo
        # anterior es la cola del registro previo: fechas, rol, monto...).
        gap = bloque[prev_end : m.start()]
        _, autores = _particionar_por_ultimo_limite(gap)
        resto = bloque[m.end() :]
        fm = _FECHA_SERVICIO_RE.match(resto)
        if fm:
            titulo = fm.group("titulo")
            anio = int(fm.group("fecha_desde")[:4])
            raw_end = m.end() + fm.end()
        else:
            titulo = resto.split(". ")[0]
            anio = None
            raw_end = m.end() + len(titulo)
        resultado.append(
            {
                "autores": autores,
                "titulo": _limpiar_titulo(titulo),
                "anio": anio,
                "raw_text": bloque[prev_end:raw_end].strip(),
            }
        )
        prev_end = m.end()
    return resultado


# --- Cargos de docencia ---------------------------------------------------
# Formato de formulario (etiqueta: valor), no de cita — a diferencia de las
# secciones anteriores esto sólo es parseable gracias a pdfplumber, que
# reconstruye el orden de lectura visual (ver docstring de _texto_completo).
#
# Las etiquetas están encadenadas en un único regex porque el orden de
# campos es fijo. CIC trunca algunas ("Dedicación horaria" sin "semanal:",
# "Nivel" sin "educativo:", "Actividades" sin "curriculares:") y además les
# saca los dos puntos — por eso esos tres campos tienen el ":" opcional.
_CAMPO_CARGO_RE = re.compile(
    r"Fecha inicio:\s*(?P<fecha_inicio>\d{2}-\d{4})\s*"
    r"Hasta:\s*(?P<hasta>\d{2}-\d{4})?\s*"
    r"Instituci[oó]n:\s*(?P<institucion>.*?)\s*"
    r"Cargo:\s*(?P<cargo>.*?)\s*"
    r"Tipo de honorarios:\s*(?P<honorarios>.*?)\s*"
    r"Dedicaci[oó]n:\s*(?P<dedicacion>.*?)\s*"
    r"Dedicaci[oó]n horaria(?:\s+semanal)?:?\s*(?P<horas>.*?)\s*"
    r"Condici[oó]n:\s*(?P<condicion>.*?)\s*"
    r"Nivel(?:\s+educativo)?:?\s*(?P<nivel>.*?)\s*"
    r"Actividades(?:\s+curriculares)?:?\s*Actividad\s+Profesor\s+responsable\s*"
    r"(?P<actividades_raw>.*?)"
    r"(?=Fecha inicio:|\Z)",
    re.DOTALL,
)


def _parsear_cargos_docencia(bloque: str) -> list[dict]:
    resultado = []
    for m in _CAMPO_CARGO_RE.finditer(bloque):
        g = m.groupdict()
        cargo = g["cargo"].strip()
        institucion = g["institucion"].strip()
        titulo = f"{cargo} - {institucion}" if institucion else cargo
        resultado.append(
            {
                "autores": None,
                "titulo": _limpiar_titulo(titulo),
                "anio": int(g["fecha_inicio"].split("-")[1]),
                "institucion": institucion,
                "cargo": cargo,
                "hasta": g["hasta"],
                "dedicacion": g["dedicacion"].strip(),
                "dedicacion_horaria": g["horas"].strip(),
                "condicion": g["condicion"].strip(),
                "nivel_educativo": g["nivel"].strip(),
                "actividades_curriculares": g["actividades_raw"].strip(),
                "raw_text": m.group(0).strip(),
            }
        )
    return resultado


# --- Secciones de formulario genéricas ------------------------------------
# Cada entrada: (nombre_ancla_de_registro, {campo: patron_etiqueta},
# funcion_que_arma_titulo_y_anio_a_partir_de_los_campos). Se usan con
# _parsear_formulario más abajo.


def _parsear_formulario(bloque: str, ancla: str, campos: dict[str, str], armar: Callable[[dict], dict]) -> list[dict]:
    resultado = []
    for trozo in _dividir_por_ancla(bloque, ancla):
        valores = _extraer_campos_por_etiquetas(trozo, campos)
        extra = armar(valores)
        resultado.append({"autores": None, "raw_text": trozo, **extra})
    return resultado


_CAMPOS_FORMACION_ACADEMICA = {
    "fecha_inicio": r"Fecha inicio:",
    "fecha_egreso": r"Fecha egreso:",
    "carrera": r"Denominaci[oó]n de la(?:\s+carrera)?:?",
    "titulo": r"T[ií]tulo:",
    "institucion": r"(?:Instituciones otorgantes del t[ií]tulo|Instituci[oó]n):",
}


def _parsear_formacion_academica(bloque: str) -> list[dict]:
    def armar(v):
        titulo = v["titulo"] or v["carrera"] or "Formación académica"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["fecha_egreso"] or v["fecha_inicio"])}

    # "Situación del nivel:" se usó de ancla en un principio, pero CIC la
    # trunca de forma inconsistente (a veces "Situación del", sin "nivel:"
    # ni ":") — "Fecha inicio:" es más confiable y alcanza porque cada
    # nivel de formación típicamente tiene un solo registro.
    return _parsear_formulario(bloque, r"Fecha inicio:", _CAMPOS_FORMACION_ACADEMICA, armar)


_CAMPOS_POSDOCTORADO = {
    "fecha_inicio": r"Fecha inicio:",
    "fecha_fin": r"Fecha finalizaci[oó]n:",
    "titulo_proyecto": r"T[ií]tulo del trabajo o proyecto de(?:\s+investigaci[oó]n)?:",
    "institucion": r"Instituci[oó]n en que realiza o realiz[oó] el curso:",
}


def _parsear_posdoctorado(bloque: str) -> list[dict]:
    def armar(v):
        titulo = v["titulo_proyecto"] or "Posdoctorado"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["fecha_inicio"])}

    return _parsear_formulario(bloque, r"Fecha inicio:", _CAMPOS_POSDOCTORADO, armar)


_CAMPOS_CURSO_EXTRACURRICULAR = {
    "fecha_inicio": r"Fecha inicio:",
    "fecha_fin": r"Fecha finalizaci[oó]n:",
    "curso": r"Denominaci[oó]n del curso:",
    "institucion": r"Instituci[oó]n en que realiza o realiz[oó] el curso:",
}


def _parsear_cursos_extracurriculares(bloque: str) -> list[dict]:
    def armar(v):
        titulo = v["curso"] or "Curso de posgrado/capacitación"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["fecha_inicio"])}

    return _parsear_formulario(bloque, r"Fecha inicio:", _CAMPOS_CURSO_EXTRACURRICULAR, armar)


_CAMPOS_IDIOMA = {
    "idioma": r"Idioma:",
    "nivel": r"Nivel de dominio del idioma:",
    "certificado": r"Certificado/s obtenido/s:",
    "institucion": r"Instituci[oó]n emisora del certificado:",
    "anio": r"Año de obtenci[oó]n del certificado:",
}


def _parsear_idiomas(bloque: str) -> list[dict]:
    def armar(v):
        titulo = f"{v['idioma']} ({v['nivel']})" if v["idioma"] and v["nivel"] else (v["idioma"] or "Idioma")
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["anio"])}

    return _parsear_formulario(bloque, r"Idioma:", _CAMPOS_IDIOMA, armar)


_CAMPOS_DOCENCIA_SIMPLE = {
    "fecha_inicio": r"Fecha inicio:",
    "hasta": r"Hasta:",
    "institucion": r"Instituci[oó]n:",
    "cargo": r"Cargo:",
}


def _parsear_docencia_simple(bloque: str) -> list[dict]:
    def armar(v):
        titulo = f"{v['cargo']} - {v['institucion']}" if v["institucion"] else (v["cargo"] or "Docencia")
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["fecha_inicio"])}

    return _parsear_formulario(bloque, r"Fecha inicio:", _CAMPOS_DOCENCIA_SIMPLE, armar)


# CARGOS EN GESTION INSTITUCIONAL: el nombre del cargo (ej. "Consejero
# Departamental") aparece en dos posiciones distintas según la instancia:
# en CONICET tiene valor normal justo después de "Cargo:"; en UNS la
# etiqueta "Cargo:" queda sin valor adyacente y el nombre real aparece como
# texto libre más adelante, entre "Dedicación horaria semanal:" y "Tipo de
# función desempeñada:". El regex captura las dos posiciones posibles
# (cargo_inline / cargo_flotante) y usa la que no esté vacía.
_CAMPO_CARGO_GESTION_RE = re.compile(
    r"Fecha inicio:\s*(?P<fecha_inicio>\d{2}/\d{2}/\d{4})\s*"
    r"Fin:\s*(?P<fin>\d{2}/\d{2}/\d{4})?\s*"
    r"Cargo:\s*(?P<cargo_inline>.*?)\s*"
    # "horas" restringido a los valores conocidos del combo de SIGEVA (no
    # un comodín genérico): con dos grupos ".*?" no-codiciosos seguidos,
    # el backtracking puede volcar todo en cargo_flotante y dejar horas
    # vacío — pasó en la práctica al validar contra UNS.
    r"Dedicaci[oó]n horaria(?:\s+semanal)?:?\s*"
    r"(?P<horas>De \d+ hasta \d+ horas|\d+ horas o m[aá]s|Entre \d+ y \d+ horas)?\s*"
    r"(?P<cargo_flotante>.*?)\s*"
    r"Tipo de funci[oó]n desempe[ñn]ada:\s*(?P<funcion>.*?)\s*"
    r"Instituci[oó]n:\s*(?P<institucion>.*?)\s*"
    r"(?=Fecha inicio:|\Z)",
    re.DOTALL,
)


def _parsear_cargos_gestion(bloque: str) -> list[dict]:
    resultado = []
    for m in _CAMPO_CARGO_GESTION_RE.finditer(bloque):
        g = m.groupdict()
        cargo = g["cargo_inline"].strip() or g["cargo_flotante"].strip()
        institucion = g["institucion"].strip()
        titulo = f"{cargo} - {institucion}" if institucion else cargo or "Cargo de gestión"
        resultado.append(
            {
                "autores": None,
                "titulo": _limpiar_titulo(titulo),
                "anio": _anio_desde_texto(g["fecha_inicio"]),
                "funcion": g["funcion"].strip(),
                "raw_text": m.group(0).strip(),
            }
        )
    return resultado


_CAMPOS_CATEGORIZACION = {
    "fecha_inicio": r"Fecha inicio:",
    "hasta": r"Hasta:",
    "anio_categorizacion": r"Año de(?:\s+categorizaci[oó]n)?:?",
    "categoria": r"Categor[ií]a en el Programa de Incentivos:",
    "institucion": r"Instituci[oó]n:",
}


def _parsear_categorizacion(bloque: str) -> list[dict]:
    def armar(v):
        titulo = f"{v['categoria']} - {v['institucion']}" if v["institucion"] else (v["categoria"] or "Categorización")
        return {
            "titulo": _limpiar_titulo(titulo),
            "anio": _anio_desde_texto(v["anio_categorizacion"] or v["fecha_inicio"]),
        }

    return _parsear_formulario(bloque, r"Fecha inicio:", _CAMPOS_CATEGORIZACION, armar)


_CAMPOS_BECARIO = {
    "anio_desde": r"Año desde:",
    "anio_hasta": r"Año(?!\s*desde)(?:\s+hasta)?:?",
    "nombre": r"Nombre/s:",
    "apellido": r"Apellido/s:",
    "institucion_trabajo": r"Instituci[oó]n de trabajo del becario:",
    "institucion_financiadora": r"Instituci[oó]n financiadora de la [Bb]eca:",
    "tipo_beca": r"Tipo de beca:",
    "funcion": r"Funci[oó]n(?:\s+desempe[ñn]ada)?:?",
}


def _parsear_becarios(bloque: str) -> list[dict]:
    def armar(v):
        if v["nombre"] or v["apellido"]:
            titulo = f"Dirección de becario/a: {v['nombre'] or ''} {v['apellido'] or ''}".strip()
        else:
            titulo = v["tipo_beca"] or "Becario/a"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["anio_desde"])}

    return _parsear_formulario(bloque, r"Año desde:", _CAMPOS_BECARIO, armar)


_CAMPOS_PROYECTO = {
    "tipo_actividad": r"Tipo de actividad de",
    "denominacion": r"Denominaci[oó]n del proyecto:",
    "fecha_desde": r"Fecha desde:",
    "fecha_hasta": r"Fecha hasta:",
    "descripcion": r"Descripci[oó]n del proyecto:",
}


def _parsear_proyectos(bloque: str) -> list[dict]:
    def armar(v):
        titulo = v["denominacion"] or "Proyecto de I+D"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["fecha_desde"])}

    return _parsear_formulario(bloque, r"Tipo de actividad de", _CAMPOS_PROYECTO, armar)


_CAMPOS_BECA_RECIBIDA = {
    "fecha_inicio": r"Fecha inicio:",
    "fin": r"Fin:",
    "tipo_beca": r"T[ií]po de beca:",
    "denominacion": r"Denominaci[oó]n de la beca:",
    "tipo_tareas": r"T[ií]po de tareas:",
    "institucion_financiadora": r"Instituci[oó]n financiadora de la [Bb]eca:",
}


def _parsear_becas_recibidas(bloque: str) -> list[dict]:
    def armar(v):
        titulo = v["denominacion"] or v["tipo_beca"] or "Beca recibida"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["fecha_inicio"])}

    return _parsear_formulario(bloque, r"Fecha inicio:", _CAMPOS_BECA_RECIBIDA, armar)


_CAMPOS_EXTENSION = {
    "titulo": r"Titulo:",
    "fecha_inicio": r"Fecha inicio:",
    "hasta": r"Hasta:",
    "funcion": r"Funci[oó]n desempe[ñn]ada:",
}


def _parsear_extension(bloque: str) -> list[dict]:
    def armar(v):
        return {"titulo": _limpiar_titulo(v["titulo"] or "Actividad de extensión"), "anio": _anio_desde_texto(v["fecha_inicio"])}

    return _parsear_formulario(bloque, r"Titulo:", _CAMPOS_EXTENSION, armar)


_CAMPOS_EVALUACION_PROYECTOS = {
    "anio_inicio": r"Año inicio:",
    "anio_fin": r"Año fin:",
    "tipo_programas": r"Tipos de programas/proyecto evaluados:",
    "institucion_convocante": r"Instituci[oó]n convocante:",
}


def _parsear_evaluacion_proyectos(bloque: str) -> list[dict]:
    def armar(v):
        titulo = v["tipo_programas"] or v["institucion_convocante"] or "Evaluación de programas/proyectos"
        return {"titulo": _limpiar_titulo(titulo), "anio": _anio_desde_texto(v["anio_inicio"])}

    return _parsear_formulario(bloque, r"Año inicio:", _CAMPOS_EVALUACION_PROYECTOS, armar)


# El nombre de la revista tiene DOS etiquetas distintas según la instancia
# (no es truncamiento): "Título de la revista:" en UNS/CIC, "Revista
# seleccionada:" en CONICET. CIC además la trunca a "Título de la", a
# veces sin los dos puntos.
_ANCLA_EVALUACION_REVISTAS_RE = r"(?:T[ií]tulo de la(?:\s+revista)?|Revista seleccionada):?"
_CAMPOS_EVALUACION_REVISTAS = {
    "titulo_revista": _ANCLA_EVALUACION_REVISTAS_RE,
    "issn": r"ISSN:",
    "anio_inicio": r"Año inicio:",
    "anio_fin": r"Año fin:",
}


def _parsear_evaluacion_revistas(bloque: str) -> list[dict]:
    def armar(v):
        return {
            "titulo": _limpiar_titulo(v["titulo_revista"] or "Evaluación de trabajos en revista"),
            "anio": _anio_desde_texto(v["anio_inicio"]),
        }

    return _parsear_formulario(bloque, _ANCLA_EVALUACION_REVISTAS_RE, _CAMPOS_EVALUACION_REVISTAS, armar)


_CAMPOS_PARTICIPACION_EVENTO = {
    "nombre_evento": r"Nombre del evento:",
    "tipo_evento": r"Tipo de evento:",
    "alcance": r"Alcance geogr[aá]fico:",
    "anio": r"Año:",
    "modo_participacion": r"Modo de participaci[oó]n:",
    "institucion_organizadora": r"Instituci[oó]n organizadora:",
}


def _parsear_participacion_eventos(bloque: str) -> list[dict]:
    def armar(v):
        return {
            "titulo": _limpiar_titulo(v["nombre_evento"] or "Participación en evento"),
            "anio": _anio_desde_texto(v["anio"]),
        }

    return _parsear_formulario(bloque, r"Nombre del evento:", _CAMPOS_PARTICIPACION_EVENTO, armar)


# --- Tesis / Demás producciones c-t publicados (fallback simple) --------
_ANIO_RE = re.compile(r"\b(19|20)\d{2}\b")


def _parsear_bloque_simple(bloque: str) -> list[dict]:
    if not bloque:
        return []
    anios = list(_ANIO_RE.finditer(bloque))
    anio = int(anios[-1].group()) if anios else None
    return [{"autores": None, "titulo": _limpiar_titulo(bloque), "anio": anio, "raw_text": bloque}]


_SECCIONES_A_PARSEAR: tuple[tuple[str, RubroTipo, Callable[[str], list[dict]]], ...] = (
    ("PUBLICACIONES - Artículos publicados en revistas:", RubroTipo.ARTICULO, _parsear_articulos),
    ("PUBLICACIONES - Trabajos en eventos c-t publicados:", RubroTipo.TRABAJO_EVENTO, _parsear_eventos),
    ("PUBLICACIONES - Tesis:", RubroTipo.TESIS, _parsear_bloque_simple),
    ("PUBLICACIONES - Demás producciones c-t publicados:", RubroTipo.OTRA_PRODUCCION_CT, _parsear_bloque_simple),
    ("SERVICIOS:", RubroTipo.SERVICIO, _parsear_servicios),
    (
        "DOCENCIA - Nivel superior universitario y/o posgrado:",
        RubroTipo.DOCENCIA,
        _parsear_cargos_docencia,
    ),
    (
        "REDES, GESTION EDITORIAL Y EVENTOS - Trabajos en eventos c-t no publicados:",
        RubroTipo.TRABAJO_EVENTO_NO_PUBLICADO,
        _parsear_eventos,
    ),
    (
        "FORMACION ACADEMICA - Nivel Universitario de Posgrado/Doctorado:",
        RubroTipo.FORMACION_ACADEMICA,
        _parsear_formacion_academica,
    ),
    (
        "FORMACION ACADEMICA - Nivel Universitario de Grado:",
        RubroTipo.FORMACION_ACADEMICA,
        _parsear_formacion_academica,
    ),
    (
        "FORMACION ACADEMICA - Nivel Terciario no Universitario:",
        RubroTipo.FORMACION_ACADEMICA,
        _parsear_formacion_academica,
    ),
    ("FORMACION COMPLEMENTARIA - Posdoctorado:", RubroTipo.FORMACION_ACADEMICA, _parsear_posdoctorado),
    (
        "FORMACION COMPLEMENTARIA - Cursos de posgrado y/o capacit. extracurriculares:",
        RubroTipo.CURSO_CAPACITACION,
        _parsear_cursos_extracurriculares,
    ),
    ("FORMACION COMPLEMENTARIA - Idiomas:", RubroTipo.CURSO_CAPACITACION, _parsear_idiomas),
    ("DOCENCIA - Nivel básico/medio:", RubroTipo.DOCENCIA, _parsear_docencia_simple),
    (
        "DOCENCIA - Cursos de posgrado y capacitaciones extracurriculares",
        RubroTipo.DOCENCIA,
        _parsear_docencia_simple,
    ),
    ("CARGOS EN GESTION INSTITUCIONAL:", RubroTipo.CARGO_GESTION, _parsear_cargos_gestion),
    (
        "CATEGORIZACION DEL PROGRAMA DE INCENTIVOS:",
        RubroTipo.CATEGORIZACION_INCENTIVOS,
        _parsear_categorizacion,
    ),
    ("FORMACION DE RRHH EN CYT - Becarios:", RubroTipo.DIRECCION_BECARIO, _parsear_becarios),
    ("FINANCIAMIENTO CYT - Proyectos I+D:", RubroTipo.PROYECTO, _parsear_proyectos),
    ("FINANCIAMIENTO CYT - Becas recibidas:", RubroTipo.BECA_RECIBIDA, _parsear_becas_recibidas),
    (
        "EXTENSION - Comunicación pública de la ciencia y la tecnología:",
        RubroTipo.EXTENSION,
        _parsear_extension,
    ),
    (
        "EVALUACION - Evaluación de programas/proyectos de I+D y/o extensión:",
        RubroTipo.EVALUACION,
        _parsear_evaluacion_proyectos,
    ),
    (
        "EVALUACION - Evaluación de trabajos en revistas CyT:",
        RubroTipo.EVALUACION,
        _parsear_evaluacion_revistas,
    ),
    (
        "REDES, GESTION EDITORIAL Y EVENTOS - Participación u organización de eventos cyt:",
        RubroTipo.PARTICIPACION_EVENTO,
        _parsear_participacion_eventos,
    ),
)


class SIGEVAPdfExtractor:
    """Extractor genérico: sirve para el CV en PDF de cualquier instancia
    SIGEVA (UNS, CONICET, CIC, CVar), ya que todas comparten el mismo
    layout de secciones."""

    def __init__(self, instancia: InstanciaSigeva):
        self.instancia = instancia

    def extraer(self, ruta: Path) -> list[AntecedenteItem]:
        texto = _texto_completo(Path(ruta))
        items: list[AntecedenteItem] = []
        for encabezado, rubro, parser in _SECCIONES_A_PARSEAR:
            bloque = _extraer_bloque_seccion(texto, encabezado)
            if not bloque:
                continue
            for reg in parser(bloque):
                items.append(
                    AntecedenteItem(
                        instancia_origen=self.instancia,
                        rubro=rubro,
                        rubro_original=encabezado.rstrip(":").strip(),
                        titulo=reg["titulo"],
                        anio=reg.get("anio"),
                        autores=_autores_desde_texto(reg.get("autores")),
                        revista_o_editorial=reg.get("revista") or reg.get("editorial"),
                        raw=reg,
                    )
                )
        return items
