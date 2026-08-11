"""Selección del modelo de chat a usar según la variable de entorno
LLM_PROVIDER (openai/gemini). Infraestructura para cuando se conecte el
resolutor semántico de `llm_semantic.py` — todavía no se invoca desde
ningún lado del grafo."""
from __future__ import annotations

import os


def get_chat_model():
    proveedor = os.getenv("LLM_PROVIDER", "openai").strip().lower()

    if proveedor == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)

    if proveedor == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"), temperature=0)

    raise ValueError(f"LLM_PROVIDER desconocido: {proveedor!r} (esperado 'openai' o 'gemini')")
