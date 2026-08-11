# Datos de ejemplo

`ejemplo_uns.json` y `ejemplo_conicet.json` simulan exports (no reales, datos
ficticios) de dos instancias SIGEVA con formatos de campo distintos, tal como
se espera que difieran las plataformas reales. Contienen, a propósito:

- **2 casos de exact match** (`UNS-001`/`CON-100234` por DOI —con distinta
  capitalización—, `UNS-002`/`CON-100235` por ISBN —con y sin guiones—).
- **2 casos de structured match** (`UNS-003`/`CON-100236` y
  `UNS-005`/`CON-100238`: mismo título normalizado + año, sin identificador
  en común).
- **1 caso de fuzzy match** (`UNS-004`/`CON-100237`: título con wording
  distinto — "aprendizaje automático" vs "machine learning" — y además
  rubro con etiqueta distinta en cada plataforma, "Artículos en Revistas"
  vs "Publicaciones Periódicas").
- **4 registros sin correspondencia** (`UNS-006`, `UNS-007` sólo en UNS;
  `CON-100239`, `CON-100240` sólo en CONICET) para ejercitar los
  antecedentes realmente desincronizados entre plataformas.

El formato exacto de export de cada SIGEVA real (UNS/CONICET/CIC/CVar) no
está confirmado todavía — estos JSON son una hipótesis razonable a partir de
la información disponible, no una copia de un export real. Cuando se defina
el formato real de cada plataforma, estos archivos (y los extractores en
`src/extractors/`) se van a tener que ajustar.
