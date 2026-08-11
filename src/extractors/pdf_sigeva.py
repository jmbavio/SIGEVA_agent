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

Limitaciones conocidas (ver README):
- El export no incluye DOI en ningún caso observado, y el ISBN tampoco
  aparece en los rubros parseados acá (no hay "Libros" con ISBN en las
  muestras usadas para validar). El nivel de exact match del diff engine
  va a disparar poco con datos de PDF.
- La separación autor/título/revista de artículos se resuelve con
  heurísticas de texto (ver `_particionar_por_ultimo_limite`), no con un
  parser gramatical completo. Funciona bien en la práctica (validado con
  ~50 registros reales) pero un título que contenga ". " seguido de
  mayúscula puede cortarse antes de lo debido (ver caso "VALVULOAORTOPATÍA
  BICÚSPIDE." en el README de datos).
- En "trabajos en eventos" el campo `autores` no se separa de forma
  confiable de la cola del registro anterior (no hay un separador fijo
  ahí) — se deja en `None`. `titulo` y `anio` sí están validados.
- CARGOS - Docencia (nivel superior) sí se parsea, con las etiquetas
  encadenadas en un único regex (`_CAMPO_CARGO_RE`) porque el formato es
  de formulario, no de cita. CIC trunca algunas etiquetas sin dos puntos
  ("Nivel" en vez de "Nivel educativo:") — contemplado en el regex.
  DOCENCIA nivel básico/medio, CARGOS EN GESTION INSTITUCIONAL,
  FINANCIAMIENTO CYT y FORMACION DE RRHH todavía no se parsean — mismo
  layout de formulario, pero con otras etiquetas; queda para una
  siguiente etapa.
- Tesis y "Demás producciones c-t publicados" se parsean con un fallback
  más simple (best-effort), validado contra un solo registro real cada
  uno — con más muestras probablemente haga falta ajustar el regex.
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

# Todos los encabezados de sección conocidos del layout SIGEVA. Se usan como
# límites al recortar el bloque de texto de una sección puntual.
ENCABEZADOS_SECCION = (
    "DATOS PERSONALES - IDENTIFICACION",
    "DATOS PERSONALES - DIRECCION RESIDENCIAL",
    "DATOS PERSONALES - LUGAR DE TRABAJO",
    "EXPERTICIA EN CYT",
    "FORMACION",
    "FORMACION ACADEMICA - Nivel Universitario de Posgrado/Doctorado:",
    "FORMACION ACADEMICA -  Nivel Universitario de Posgrado/Doctorado:",
    "FORMACION ACADEMICA - Nivel Universitario de Grado:",
    "FORMACION ACADEMICA -  Nivel Universitario de Grado:",
    "FORMACION ACADEMICA - Nivel Terciario no Universitario:",
    "FORMACION ACADEMICA -  Nivel Terciario no Universitario:",
    "FORMACION ACADEMICA -Nivel Terciario no Universitario:",
    "FORMACION COMPLEMENTARIA -  Posdoctorado:",
    "FORMACION COMPLEMENTARIA -  Cursos de posgrado y/o capacit. extracurriculares:",
    "FORMACION COMPLEMENTARIA -  Idiomas:",
    "CARGOS",
    "DOCENCIA - Nivel superior universitario y/o posgrado:",
    "DOCENCIA - Nivel básico/medio:",
    "DOCENCIA - Cursos de posgrado y capacitaciones extracurriculares",
    "CARGOS EN GESTION INSTITUCIONAL:",
    "CATEGORIZACION DEL PROGRAMA DE INCENTIVOS:",
    "ANTECEDENTES",
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
