from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from mededge_rag.pipeline import ask


st.set_page_config(page_title="MedEdge RAG", layout="wide")

st.title("MedEdge RAG")

index_path = st.sidebar.text_input("Index path", str(ROOT / "data" / "index" / "mededge_index.json"))
top_k = st.sidebar.slider("Top-k", min_value=1, max_value=5, value=3)
use_llm = st.sidebar.checkbox("Use local Ollama LLM", value=True)

question = st.text_input("의료 질문", "아이가 고열일 때 언제 응급실에 가야 하나요?")

if st.button("Ask", type="primary"):
    try:
        answer, evidence = ask(index_path, question, top_k=top_k, use_llm=use_llm)
    except Exception as exc:
        st.error(str(exc))
    else:
        st.subheader("Answer")
        st.write(answer)
        st.subheader("Evidence")
        st.dataframe(evidence, use_container_width=True)
