# SIGEVA Sync & Audit Agent (Diff Engine)

Agente que audita y compara antecedentes académicos (artículos, libros,
docencia, proyectos, etc.) cargados por separado en distintas instancias de
SIGEVA (UNS, CONICET, CIC, CVar), para detectar cuándo se desincronizan.

Lee datos desde el PDF de "Curriculum vitae" que exporta cada instancia
SIGEVA, o desde exports JSON de ejemplo — todavía no hay login ni scraping
en vivo contra SIGEVA.

## Estructura

```
sigeva_agent/
├── src/
│   ├── graph/          # grafo de estados (LangGraph)
│   ├── extractors/      # lectura de exports de cada instancia SIGEVA (PDF/JSON)
│   ├── matching/        # diff engine: exact / structured / fuzzy (+ gancho LLM)
│   ├── models/           # esquema homologado de antecedente (Pydantic)
│   └── reports/          # generación del reporte de diferencias
├── tests/
├── data/                 # datos de ejemplo (ficticios, no reales)
├── .env.example
├── requirements.txt
└── main.py
```

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # sólo necesario si se va a usar el resolutor LLM
```

## Uso

```bash
python main.py
```

Por defecto corre el grafo de diff sobre `data/ejemplo_uns.json` y
`data/ejemplo_conicet.json` (datos de ejemplo ficticios), e imprime en
stdout un reporte en Markdown con los antecedentes emparejados (y por qué
nivel: exacto/estructurado/fuzzy) y los que están sólo en una de las dos
instancias.

### Usar tus propios PDFs de SIGEVA

Cada instancia SIGEVA te deja descargar tu "Curriculum vitae" en PDF desde
tu propio panel. Para correr el diff sobre tus PDFs reales (nunca se
versionan — ver `.gitignore`), seteá en tu `.env`:

```bash
SIGEVA_RUTA_A=/ruta/local/a/tu_cv_uns.pdf
SIGEVA_INSTANCIA_A=UNS
SIGEVA_RUTA_B=/ruta/local/a/tu_cv_conicet.pdf
SIGEVA_INSTANCIA_B=CONICET
```

Instancias válidas: `UNS`, `CONICET`, `CIC`, `CVAR`. El parser de PDF
(`src/extractors/pdf_sigeva.py`) es genérico: las cuatro instancias
comparten el mismo layout de secciones (mismo software SIGEVA, distinta
marca institucional), así que sirve para cualquiera sin cambios — validado
contra exports reales de tres de las cuatro (UNS, CIC, CONICET).

## Tests

```bash
pytest
```

## Cómo funciona el diff engine

Prioridad de matching, en `src/matching/engine.py`:

1. **Exact match** — DOI o ISBN en común (case/formato-insensitive). En la
   práctica dispara poco: el export en PDF no incluye DOI en ningún caso
   observado hasta ahora.
2. **Structured match** — título normalizado (minúsculas, sin tildes, sin
   puntuación) + año en común. Es el nivel que más resuelve con datos de
   PDF.
3. **Fuzzy match** — similitud de Levenshtein sobre el título normalizado,
   con umbral configurable (`umbral_fuzzy`, default 85).

Lo que no matchea en ninguno de los tres niveles queda disponible para un
futuro resolutor semántico vía LLM (`src/matching/llm_semantic.py` — sólo
la interfaz, todavía no implementado) para casos ambiguos como rubros con
etiquetas distintas entre plataformas (ej. "Artículos en Revistas" vs
"Publicaciones Periódicas").

## El parser de PDF: qué sí y qué no

Validado contra exports reales de tres instancias distintas (UNS, CIC,
CONICET) — mismo layout de secciones, sirve sin cambios. Usa `pdfplumber`
(no `pypdf`) porque reconstruye el orden de lectura visual del PDF; esto es
imprescindible para las secciones con formato de formulario en dos
columnas, donde `pypdf` devuelve etiquetas y valores en el orden del
content stream (todas las etiquetas de un lado, después todos los valores),
no en el orden en que se ven en pantalla.

Parsea:
- **Citas** (artículos, trabajos en eventos publicados/no publicados,
  tesis, demás producciones, servicios).
- **CARGOS - Docencia** (nivel superior universitario/posgrado): formato
  de formulario etiqueta-valor, con un único regex encadenado porque el
  orden de campos es fijo. Detectó desincronizaciones reales entre
  instancias (un cargo docente presente en una plataforma y ausente en las
  otras, una fecha de fin de cargo que difiere).

Limitaciones conocidas — ver el docstring de `src/extractors/pdf_sigeva.py`
para el detalle:

- No hay DOI/ISBN en los PDFs de CV observados hasta ahora.
- El campo `autores` de "trabajos en eventos" no se separa de forma
  confiable de la cola del registro anterior (no hay un separador fijo
  ahí) — se deja en `None` en vez de guardar un dato sucio; `titulo` y
  `anio` sí están validados.
- Un título que contenga ". " seguido de mayúscula puede cortarse antes de
  lo debido (heurística de texto, no un parser gramatical completo).
- DOCENCIA nivel básico/medio, CARGOS EN GESTION INSTITUCIONAL,
  FINANCIAMIENTO CYT y FORMACION DE RRHH usan el mismo tipo de layout de
  formulario que CARGOS - Docencia pero con otras etiquetas — no se
  parsean todavía, queda para una etapa siguiente.

## Estado de los datos

Los JSON de ejemplo en `data/` son ficticios (no un export real) — ver
`data/README.md` para el detalle de qué casos de matching prueba cada
registro. El rubro `RubroTipo` está basado en la taxonomía real del "Banco
de Datos" de SIGEVA/CONICET, confirmada además contra tres PDFs de CV
reales de tres instancias distintas.
