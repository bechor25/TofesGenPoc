"""Streamlit UI — end-to-end: upload document -> extract canonical template
-> human review gate -> generate QA population -> render filled documents.
Also exposes the blank template (source of truth) and filling it with your own data.

Run with:  uv run streamlit run src/doc2tests/ui/app.py
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from doc2tests.contracts.enums import SourceKind
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import GraphState, InputRef, RunConfig
from doc2tests.contracts.template import CanonicalTemplate
from doc2tests.ingest.loaders import detect_kind, load_images
from doc2tests.orchestrator.config import build_vision_provider
from doc2tests.orchestrator.graph import build_graph
from doc2tests.render.canonical import (
    dataset_csv,
    dataset_json,
    records_from_rows,
    render_blank_docx,
    render_blank_html,
    template_json,
)
from doc2tests.render.docx import render_docx
from doc2tests.render.html import render_html
from doc2tests.render.layout import fill_layout

load_dotenv()

OUTPUT_ROOT = Path("output")
st.set_page_config(page_title="doc2tests", page_icon="📄", layout="wide")

st.markdown("""
<style>
  .stApp { direction: rtl; }
  .stApp, .stMarkdown, .stMarkdown p, label, h1, h2, h3, .stMetricLabel { text-align: right; }
  section[data-testid="stSidebar"] { direction: rtl; text-align: right; }
  h1, h2, h3 { font-family: 'Assistant','Segoe UI',Arial,sans-serif; }
  .stButton>button { background: linear-gradient(135deg,#2b5cb8,#3a6fd0); color:#fff;
     border:0; border-radius:10px; padding:.5rem 1.2rem; font-weight:600; }
  .stButton>button:hover { filter:brightness(1.08); }
  .stDownloadButton>button { border-radius:9px; }
  div[data-testid="stMetric"] { background:#f4f7fc; border:1px solid #e6e8ee;
     border-radius:12px; padding:12px 16px; }
  .hint { color:#6b7280; font-size:.85rem; }
</style>
""", unsafe_allow_html=True)

st.title("📄 doc2tests — מסמך → אוכלוסיית בדיקות")
st.markdown(
    '<div class="hint">חילוץ טמפלייט קנוני מכל מסמך, יצירת דאטת בדיקות, ומילוי מסמכים.</div>',
    unsafe_allow_html=True,
)


def _reset() -> None:
    for k in ("graph", "thread_id", "phase", "template", "out_dir", "final", "errors"):
        st.session_state.pop(k, None)


def _download_row(template: CanonicalTemplate, out_dir: Path) -> None:
    """Blank-template artifacts: HTML preview + HTML/DOCX/JSON downloads."""
    with st.expander("📄 המסמך כטמפלייט — ללא ערכים (מקור האמת)", expanded=False):
        blank_html = render_blank_html(template)
        st.components.v1.html(blank_html, height=300, scrolling=True)
        blank_docx_path = out_dir / "template.docx"
        render_blank_docx(template, str(blank_docx_path))
        c1, c2, c3 = st.columns(3)
        c1.download_button("⬇ טמפלייט HTML", blank_html, file_name="template.html",
                           mime="text/html")
        c2.download_button("⬇ טמפלייט DOCX (docxtpl)", blank_docx_path.read_bytes(),
                           file_name="template.docx")
        c3.download_button("⬇ טמפלייט JSON", template_json(template),
                           file_name="template.json", mime="application/json")
        st.markdown('<div class="hint">ה-DOCX מכיל <code>{{ placeholders }}</code> '
                    'וניתן למילוי חוזר עם כל דאטה.</div>', unsafe_allow_html=True)


def _layout_section(template: CanonicalTemplate, record: Record | None = None) -> None:
    """The faithful digital RECREATION of the source document (same design),
    empty as a template or filled with a record. Available for image/PDF sources."""
    layout = st.session_state.get("layout_html")
    if not layout:
        return
    if record is None:
        values = {f.id: "" for f in template.fields}          # clear all slots
    else:
        values = {f.id: "" for f in template.fields}
        values.update({fid: v.value for fid, v in record.values.items()})
    html = fill_layout(layout, values)
    title = ("🎯 טמפלייט משוחזר — עיצוב זהה למקור, ללא ערכים" if record is None
             else "🎯 מסמך ממולא — עיצוב זהה למקור")
    with st.expander(title, expanded=True):
        st.components.v1.html(html, height=620, scrolling=True)
        fname = "template.html" if record is None else "filled.html"
        st.download_button(f"⬇ {fname}", html, file_name=fname, mime="text/html",
                           key=f"lay_{fname}_{record.index if record else 'blank'}")
        st.markdown('<div class="hint">שוחזר ע"י המודל מתוך המסמך המקורי. '
                    'ניתן להוריד ולמלא שוב ושוב עם כל דאטה.</div>', unsafe_allow_html=True)


def _custom_fill_section(template: CanonicalTemplate, out_dir: Path) -> None:
    """Fill the template with the user's OWN test data."""
    with st.expander("✍️ מלא את הטמפלייט בנתונים שלך", expanded=False):
        field_ids = [f.id for f in template.fields]
        example = json.dumps([{fid: "" for fid in field_ids}], ensure_ascii=False, indent=2)
        st.markdown('<div class="hint">הדבק מערך JSON של רשומות (מפתח = מזהה שדה). '
                    'שדות זמינים: ' + ", ".join(f"<code>{f}</code>" for f in field_ids)
                    + "</div>", unsafe_allow_html=True)
        raw = st.text_area("רשומות JSON", value=example, height=160, key="custom_json")
        if st.button("מלא מסמכים מהנתונים שלי ▶"):
            try:
                rows = json.loads(raw)
                assert isinstance(rows, list)
            except (json.JSONDecodeError, AssertionError):
                st.error("JSON לא תקין — נדרש מערך של אובייקטים.")
                return
            recs = records_from_rows(template, rows)
            custom_dir = out_dir / "custom"
            custom_dir.mkdir(parents=True, exist_ok=True)
            layout = st.session_state.get("layout_html")
            st.success(f"מולאו {len(recs)} מסמכים " +
                       ("על הטמפלייט המשוחזר (עיצוב זהה)." if layout
                        else "(תצוגת טבלה — אין טמפלייט משוחזר)."))
            for r in recs:
                values = {f.id: "" for f in template.fields}
                values.update({fid: v.value for fid, v in r.values.items()})
                html = fill_layout(layout, values) if layout else render_html(template, r)
                docx_path = custom_dir / f"custom_{r.index:03d}.docx"
                render_docx(template, r, str(docx_path))
                st.components.v1.html(html, height=620 if layout else 260, scrolling=True)
                d1, d2 = st.columns(2)
                d1.download_button(f"⬇ HTML #{r.index}", html,
                                   file_name=f"custom_{r.index}.html", mime="text/html",
                                   key=f"ch_{r.index}")
                d2.download_button(f"⬇ DOCX #{r.index}", docx_path.read_bytes(),
                                   file_name=f"custom_{r.index}.docx", key=f"cd_{r.index}")


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ הגדרות")
    n = st.number_input("גודל אוכלוסייה (N)", min_value=1, max_value=500, value=20)
    formats = st.multiselect("פורמטים", ["html", "docx"], default=["html", "docx"])
    seed = st.number_input("seed", min_value=0, value=42)
    if st.button("🔄 איפוס"):
        _reset()
        st.rerun()

if not os.getenv("OPENAI_API_KEY"):
    st.error("חסר OPENAI_API_KEY בקובץ .env — נדרש לשלב החילוץ (vision).")
    st.stop()

phase = st.session_state.get("phase", "start")

# ------------------------------------------------------------------ start
if phase == "start":
    st.subheader("1 · העלאת מסמך")
    uploaded = st.file_uploader("צילום / סריקה / PDF / Word של טופס (כתב-יד או מודפס)",
                                type=["jpg", "jpeg", "png", "pdf", "docx"])
    if uploaded is not None:
        suffix = Path(uploaded.name).suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png"):
            st.image(uploaded, caption="המסמך שהועלה", width=380)
        else:
            st.info(f"📎 {uploaded.name}")
        if st.button("חלץ טמפלייט ▶", type="primary"):
            thread_id = f"ui-{abs(hash(uploaded.name)) % 100000}"
            out_dir = OUTPUT_ROOT / thread_id
            out_dir.mkdir(parents=True, exist_ok=True)
            input_path = out_dir / f"input{suffix}"
            input_path.write_bytes(uploaded.getvalue())
            kind = SourceKind(detect_kind(str(input_path)))
            # background image for the exact-layout overlay
            bg_bytes: bytes | None
            if suffix in (".jpg", ".jpeg", ".png"):
                bg_bytes = uploaded.getvalue()
                bg_mime = "image/png" if suffix == ".png" else "image/jpeg"
            elif suffix == ".pdf":
                imgs = load_images(str(input_path))
                bg_bytes = imgs[0] if imgs else None
                bg_mime = "image/png"
            else:
                bg_bytes, bg_mime = None, "image/jpeg"
            with st.spinner("מחלץ שדות + קואורדינטות (vision + OCR מקומי)..."):
                graph = build_graph(build_vision_provider(), str(out_dir))
                config = {"configurable": {"thread_id": thread_id}}
                graph.invoke(GraphState(
                    input_ref=InputRef(path=str(input_path), kind=kind),
                    config=RunConfig(n=int(n), seed=int(seed), formats=list(formats)),
                ), config)
                snap = graph.get_state(config)
            st.session_state.update(
                graph=graph, thread_id=thread_id, out_dir=str(out_dir),
                template=snap.values["template"], errors=snap.values.get("errors", []),
                layout_html=snap.values.get("layout_html"),
                bg_bytes=bg_bytes, bg_mime=bg_mime, phase="review",
            )
            st.rerun()

# ------------------------------------------------------------------ review
elif phase == "review":
    st.subheader("2 · שער סקירה — אישור / עריכת הטמפלייט")
    template = st.session_state["template"]
    out_dir = Path(st.session_state["out_dir"])
    if st.session_state.get("errors"):
        st.warning("שגיאות בחילוץ: " + "; ".join(e.message for e in st.session_state["errors"]))
    st.caption(f"סוג מסמך: {template.doc_type} · {len(template.fields)} שדות זוהו")

    _layout_section(template)
    _download_row(template, out_dir)

    st.markdown("**שדות שזוהו** (ניתן לערוך תוויות):")
    edits: dict[str, str] = {}
    h1, h2, h3 = st.columns([3, 2, 1])
    h1.caption("תווית")
    h2.caption("טיפוס")
    h3.caption("PII")
    for f in template.fields:
        c1, c2, c3 = st.columns([3, 2, 1])
        new_label = c1.text_input(f.id, value=f.label, key=f"lbl_{f.id}",
                                  label_visibility="collapsed")
        c2.text_input("t", value=f.type.value, key=f"typ_{f.id}", disabled=True,
                      label_visibility="collapsed")
        c3.text_input("p", value="🔒" if f.pii else "—", key=f"pii_{f.id}", disabled=True,
                      label_visibility="collapsed")
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
            st.session_state["final"] = graph.invoke(None, config)
        st.session_state["template"] = st.session_state["final"]["template"]
        st.session_state["phase"] = "done"
        st.rerun()

# ------------------------------------------------------------------ done
elif phase == "done":
    st.subheader("3 · תוצאות")
    final = st.session_state["final"]
    template = final["template"]
    population, coverage, outputs = final["population"], final["coverage"], final["outputs"]
    out_dir = Path(st.session_state["out_dir"])

    c1, c2, c3 = st.columns(3)
    c1.metric("רשומות", len(population))
    c2.metric("מסמכים", len(outputs))
    c3.metric("כללים שנבדקו", len(coverage.rules_exercised) if coverage else 0)

    dist = Counter(r.test_class.value for r in population)
    st.markdown("**התפלגות מחלקות בדיקה:** " +
                " · ".join(f"{k}: {v}" for k, v in dist.items()))
    if coverage and coverage.rules_exercised:
        st.markdown("**כללים שהופעלו:** " + ", ".join(coverage.rules_exercised))
    if coverage and coverage.gaps:
        st.markdown("**פערי כיסוי:** " + "; ".join(coverage.gaps))

    _layout_section(template, population[0] if population else None)
    _download_row(template, out_dir)

    st.markdown("**⬇ ייצוא dataset:**")
    d1, d2 = st.columns(2)
    d1.download_button("dataset JSON", dataset_json(population),
                       file_name="dataset.json", mime="application/json")
    d2.download_button("dataset CSV", dataset_csv(template, population),
                       file_name="dataset.csv", mime="text/csv")

    st.markdown("**רשומות (10 ראשונות):**")
    st.dataframe([
        {"#": r.index, "class": r.test_class.value, "valid": r.expected_valid,
         "violates": r.violates or "", **{fid: v.value for fid, v in r.values.items()}}
        for r in population[:10]
    ], use_container_width=True)

    with st.expander("📊 גרסת טבלת-נתונים (לא הטמפלייט) + הורדות", expanded=False):
        st.caption("תצוגה מובנית לנוחות בדיקה. הטמפלייט המדויק הוא ה-overlay למעלה 🎯")
        html_docs = [d for d in outputs if d.fmt == "html"]
        if html_docs:
            st.components.v1.html(Path(html_docs[0].path).read_text(encoding="utf-8"),
                                  height=300, scrolling=True)
        for d in outputs[:20]:
            p = Path(d.path)
            if p.exists():
                st.download_button(f"⬇ {p.name}", p.read_bytes(), file_name=p.name, key=d.path)

    _custom_fill_section(template, out_dir)

    if st.button("🆕 הרצה חדשה"):
        _reset()
        st.rerun()
