# SIGEVA Sync & Audit Agent (Diff Engine)

Agente que audita y compara antecedentes académicos (artículos, libros,
docencia, proyectos, etc.) cargados por separado en distintas instancias de
SIGEVA (UNS, CONICET, CIC, CVar), para detectar cuándo se desincronizan.

Por ahora sólo lee datos desde exports JSON locales (`data/`) — todavía no
hay login ni scraping en vivo contra SIGEVA.

## Estructura

```
sigeva_agent/
├── src/
│   ├── graph/          # grafo de estados (LangGraph)
│   ├── extractors/      # lectura de exports de cada instancia SIGEVA
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

Corre el grafo de diff sobre `data/ejemplo_uns.json` y
`data/ejemplo_conicet.json`, e imprime en stdout un reporte en Markdown con
los antecedentes emparejados (y por qué nivel: exacto/estructurado/fuzzy) y
los que están sólo en una de las dos instancias.

## Tests

```bash
pytest
```

## Cómo funciona el diff engine

Prioridad de matching, en `src/matching/engine.py`:

1. **Exact match** — DOI o ISBN en común (case/formato-insensitive).
2. **Structured match** — título normalizado (minúsculas, sin tildes, sin
   puntuación) + año en común.
3. **Fuzzy match** — similitud de Levenshtein sobre el título normalizado,
   con umbral configurable (`umbral_fuzzy`, default 85).

Lo que no matchea en ninguno de los tres niveles queda disponible para un
futuro resolutor semántico vía LLM (`src/matching/llm_semantic.py` — sólo
la interfaz, todavía no implementado) para casos ambiguos como rubros con
etiquetas distintas entre plataformas (ej. "Artículos en Revistas" vs
"Publicaciones Periódicas").

## Estado de los datos

El formato real de export de cada instancia SIGEVA (UNS/CONICET/CIC/CVar)
todavía no está confirmado. Los extractores en `src/extractors/` y los JSON
de ejemplo en `data/` son una hipótesis de trabajo razonable, no una copia
de un export real — ver `data/README.md` para el detalle de qué casos
prueba cada registro de ejemplo. El rubro `RubroTipo` sí está basado en la
taxonomía real del "Banco de Datos" de SIGEVA/CONICET.
