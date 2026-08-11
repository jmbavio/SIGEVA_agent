"""UI en Streamlit: subís 2 PDFs de CV de SIGEVA y ves el reporte de
diferencias en el navegador, sin tocar la terminal ni variables de
entorno. Wrapper fino sobre el mismo grafo que usa main.py — no duplica
lógica de extracción ni de matching.

Correr con: streamlit run app.py"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from src.graph.build import RECURSION_LIMIT, construir_grafo
from src.models.schema import InstanciaSigeva

st.set_page_config(page_title="SIGEVA Sync & Audit Agent", page_icon="🔍")
st.title("SIGEVA Sync & Audit Agent")
st.caption(
    "Comparación de antecedentes académicos entre dos instancias SIGEVA. "
    "Los PDFs que subís no se guardan — se procesan en memoria/temporal y se borran al terminar."
)

INSTANCIAS = [i.value for i in InstanciaSigeva]

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Instancia A")
    archivo_a = st.file_uploader("PDF de CV", type="pdf", key="archivo_a")
    instancia_a = st.selectbox("Instancia", INSTANCIAS, index=0, key="instancia_a")
with col_b:
    st.subheader("Instancia B")
    archivo_b = st.file_uploader("PDF de CV", type="pdf", key="archivo_b")
    instancia_b = st.selectbox("Instancia", INSTANCIAS, index=1, key="instancia_b")

usar_llm = st.checkbox(
    "Usar resolutor semántico LLM para los antecedentes que no matcheen (consume tu API key)",
    value=False,
)
if usar_llm:
    st.info(
        "Necesita LLM_PROVIDER y la API key correspondiente (OPENAI_API_KEY o GOOGLE_API_KEY) "
        "configurados en tu .env antes de correr la app."
    )

comparar = st.button("Comparar", type="primary", disabled=not (archivo_a and archivo_b))

if comparar:
    os.environ["SIGEVA_USAR_LLM_SEMANTICO"] = "true" if usar_llm else "false"

    with tempfile.TemporaryDirectory() as directorio_temp:
        ruta_a = Path(directorio_temp) / "cv_a.pdf"
        ruta_b = Path(directorio_temp) / "cv_b.pdf"
        ruta_a.write_bytes(archivo_a.getvalue())
        ruta_b.write_bytes(archivo_b.getvalue())

        estado_inicial = {
            "ruta_a": str(ruta_a),
            "instancia_a": InstanciaSigeva(instancia_a),
            "ruta_b": str(ruta_b),
            "instancia_b": InstanciaSigeva(instancia_b),
        }
        config = {"configurable": {"thread_id": "diff-ui"}, "recursion_limit": RECURSION_LIMIT}

        with st.spinner("Extrayendo y comparando antecedentes..."):
            grafo = construir_grafo()
            estado_final = grafo.invoke(estado_inicial, config=config)

    st.markdown(estado_final["reporte_md"])
