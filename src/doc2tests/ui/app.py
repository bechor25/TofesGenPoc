"""Streamlit UI — end-to-end run: upload document -> extract canonical template
-> human review gate -> generate QA population -> render filled documents.

Run with:  uv run streamlit run src/doc2tests/ui/app.py
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.orchestrator.config import build_vision_provider
from doc2tests.orchestrator.graph import build_graph

load_dotenv()

OUTPUT_ROOT = Path("output")
st.set_page_config(page_title="doc2tests", layout="wide")
st.markdown('<div dir="rtl">', unsafe_allow_html=True)
st.title("doc2tests — מסמך → אוכלוסיית בדיקות")


def _reset() -> None:
    for k in ("graph", "thread_id", "phase", "template", "out_dir"):
        st.session_state.pop(k, None)


def _has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("הגדרות")
    n = st.number_input("גודל אוכלוסייה (N)", min_value=1, max_value=500, value=20)
    formats = st.multiselect("פורמטים", ["html", "docx"], default=["html", "docx"])
    seed = st.number_input("seed", min_value=0, value=42)
    if st.button("איפוס"):
        _reset()
        st.rerun()

if not _has_key():
    st.error("חסר OPENAI_API_KEY בקובץ .env — נדרש לשלב החילוץ (vision).")
    st.stop()

phase = st.session_state.get("phase", "start")

# ---------------------------------------------------------------- phase: start
if phase == "start":
    st.subheader("1. העלאת מסמך")
    uploaded = st.file_uploader("צילום / סריקה של טופס", type=["jpg", "jpeg", "png"])
    if uploaded is not None:
        st.image(uploaded, caption="המסמך שהועלה", width=380)
        if st.button("חלץ טמפלייט ▶", type="primary"):
            thread_id = f"ui-{abs(hash(uploaded.name)) % 100000}"
            out_dir = OUTPUT_ROOT / thread_id
            out_dir.mkdir(parents=True, exist_ok=True)
            input_path = out_dir / "input.jpg"
            input_path.write_bytes(uploaded.getvalue())

            with st.spinner("מריץ OCR + חילוץ שדות (OpenAI vision)..."):
                graph = build_graph(build_vision_provider(), str(out_dir))
                config = {"configurable": {"thread_id": thread_id}}
                state = GraphState(
                    input_ref=InputRef(path=str(input_path), kind=SourceKind.image),
                    config=RunConfig(n=int(n), seed=int(seed), formats=list(formats)),
                )
                graph.invoke(state, config)
                snap = graph.get_state(config)

            st.session_state["graph"] = graph
            st.session_state["thread_id"] = thread_id
            st.session_state["out_dir"] = str(out_dir)
            st.session_state["template"] = snap.values["template"]
            st.session_state["errors"] = snap.values.get("errors", [])
            st.session_state["phase"] = "review"
            st.rerun()

# ---------------------------------------------------------------- phase: review
elif phase == "review":
    st.subheader("2. שער סקירה — אישור / עריכת הטמפלייט")
    template = st.session_state["template"]
    errors = st.session_state.get("errors", [])
    if errors:
        st.warning("שגיאות בחילוץ: " + "; ".join(e.message for e in errors))

    st.caption(f"סוג מסמך: {template.doc_type} · {len(template.fields)} שדות זוהו")
    edits: dict[str, str] = {}
    for f in template.fields:
        c1, c2, c3 = st.columns([3, 2, 2])
        new_label = c1.text_input(f"תווית ({f.id})", value=f.label, key=f"lbl_{f.id}")
        c2.text_input("טיפוס", value=f.type.value, key=f"typ_{f.id}", disabled=True)
        c3.text_input("PII", value="כן" if f.pii else "לא", key=f"pii_{f.id}", disabled=True)
        if new_label != f.label:
            edits[f.id] = new_label

    rels = [r for r in template.relations if r.kind == "order"]
    if rels:
        st.caption("יחסים: " + ", ".join(f"{r.left} {r.op.value} {r.right}" for r in rels))

    if st.button("אשר וייצר אוכלוסייה ▶", type="primary"):
        graph = st.session_state["graph"]
        config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
        graph.update_state(config, {"review": {"approved": True, "edits": edits}})
        with st.spinner("מייצר אוכלוסיית בדיקות ומרנדר מסמכים..."):
            final = graph.invoke(None, config)
        st.session_state["final"] = final
        st.session_state["phase"] = "done"
        st.rerun()

# ---------------------------------------------------------------- phase: done
elif phase == "done":
    st.subheader("3. תוצאות")
    final = st.session_state["final"]
    population = final["population"]
    coverage = final["coverage"]
    outputs = final["outputs"]

    col1, col2, col3 = st.columns(3)
    col1.metric("רשומות", len(population))
    col2.metric("מסמכים", len(outputs))
    col3.metric("כללים שנבדקו", len(coverage.rules_exercised) if coverage else 0)

    st.markdown("**התפלגות מחלקות בדיקה:**")
    from collections import Counter
    dist = Counter(r.test_class.value for r in population)
    st.write({k: v for k, v in dist.items()})

    if coverage and coverage.rules_exercised:
        st.markdown("**כללים שהופעלו (negative):** " + ", ".join(coverage.rules_exercised))
    if coverage and coverage.gaps:
        st.markdown("**פערי כיסוי:** " + "; ".join(coverage.gaps))

    st.markdown("**רשומות (10 ראשונות):**")
    st.dataframe([
        {"#": r.index, "class": r.test_class.value, "valid": r.expected_valid,
         "violates": r.violates or "", **{fid: v.value for fid, v in r.values.items()}}
        for r in population[:10]
    ])

    st.markdown("**מסמכים שנוצרו:**")
    html_docs = [d for d in outputs if d.fmt == "html"]
    if html_docs:
        preview = Path(html_docs[0].path).read_text(encoding="utf-8")
        st.components.v1.html(preview, height=320, scrolling=True)
    for d in outputs[:20]:
        p = Path(d.path)
        if p.exists():
            st.download_button(f"⬇ {p.name}", p.read_bytes(), file_name=p.name, key=d.path)

    if st.button("הרצה חדשה"):
        _reset()
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
