"""Streamlit UI for the image-edit pipeline (RTL, Hebrew).

Flow: upload form -> detect values -> review/add/pick N -> generate valid variants
-> gpt-image-2 edits the original per variant -> download images.
Run: uv run streamlit run src/doc2tests/ui/app.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from doc2tests.common.logging import recent_logs
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import (
    DetectedValue,
    GraphState,
    InputRef,
    ReviewDecision,
)
from doc2tests.ingest.loaders import detect_kind
from doc2tests.orchestrator.config import build_provider
from doc2tests.orchestrator.graph import build_graph
from doc2tests.ui.helpers import records_to_rows, zip_images

load_dotenv()

st.set_page_config(page_title="מחולל טפסים", layout="wide")
st.markdown(
    "<style>body,.stApp{direction:rtl;text-align:right}"
    ".stDataFrame,.stDataEditor{direction:rtl}</style>", unsafe_allow_html=True)

_STEPS = ["העלאה", "זיהוי ערכים", "סקירה ואישור", "יצירה ומילוי", "הורדה"]


def _stepper(active: int) -> None:
    cols = st.columns(len(_STEPS))
    for i, (c, name) in enumerate(zip(cols, _STEPS, strict=True)):
        mark = "✅" if i < active else ("🔵" if i == active else "⚪")
        c.markdown(f"{mark} **{name}**")


def _save_upload(uploaded) -> str:
    suffix = Path(uploaded.name).suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getbuffer())
    return path


def _thread_cfg() -> dict:
    return {"configurable": {"thread_id": st.session_state["thread_id"]}}


def main() -> None:
    st.title("מחולל טפסים — החלפת ערכים בתמונה")
    if "phase" not in st.session_state:
        st.session_state["phase"] = "upload"

    phase = st.session_state["phase"]
    _stepper({"upload": 0, "review": 2, "done": 4}[phase])

    if not os.getenv("OPENAI_API_KEY"):
        st.error("חסר OPENAI_API_KEY בקובץ .env")
        return

    if phase == "upload":
        _upload_phase()
    elif phase == "review":
        _review_phase()
    elif phase == "done":
        _done_phase()

    with st.sidebar.expander("לוגים", expanded=False):
        st.code("\n".join(recent_logs(120)) or "—")


def _upload_phase() -> None:
    uploaded = st.file_uploader("העלה טופס", type=["jpg", "jpeg", "png", "pdf", "docx"])
    if uploaded and st.button("זהה ערכים", type="primary"):
        path = _save_upload(uploaded)
        st.session_state["thread_id"] = uploaded.name
        app = build_graph(build_provider())
        init = GraphState(
            input_ref=InputRef(path=path, kind=SourceKind(detect_kind(path))))
        with st.spinner("מזהה ערכים..."):
            app.invoke(init, _thread_cfg())
        st.session_state["app"] = app
        snap = app.get_state(_thread_cfg())
        st.session_state["detected"] = [d.model_dump() for d in snap.values["detected"]]
        st.session_state["page_images"] = snap.values["page_images"]
        st.session_state["phase"] = "review"
        st.rerun()


def _review_phase() -> None:
    imgs = st.session_state.get("page_images") or []
    if imgs:
        st.image(imgs[0], caption="הטופס שנקלט", width=380)

    st.subheader("ערכים שזוהו — אשר, ערוך, או הוסף")
    st.caption("סמן 'אישי?' לכל ערך שיש להחליף. הוסף שורות לערכים שלא זוהו.")
    rows = [
        {"label": d["label"], "value": d["value"],
         "field_type": d["field_type"], "אישי?": d["is_personal"]}
        for d in st.session_state["detected"]
    ]
    edited = st.data_editor(
        rows, num_rows="dynamic", use_container_width=True,
        column_config={
            "field_type": st.column_config.SelectboxColumn(
                "סוג", options=[t.value for t in FieldType]),
            "אישי?": st.column_config.CheckboxColumn("אישי?"),
        },
    )
    n = st.number_input("כמה וריאציות ליצור?", min_value=1, max_value=50, value=10)

    if st.button("צור טפסים", type="primary"):
        from doc2tests.common.slug import unique_slug
        values: list[DetectedValue] = []
        seen: list[str] = []
        for r in edited:
            label = str(r.get("label", "")).strip()
            val = str(r.get("value", "")).strip()
            if not label and not val:
                continue
            fid = unique_slug(label or val, seen)
            seen.append(fid)
            values.append(DetectedValue(
                id=fid, label=label, value=val,
                field_type=FieldType(r.get("field_type") or "free_text"),
                is_personal=bool(r.get("אישי?")),
            ))
        app = st.session_state["app"]
        cfg = _thread_cfg()
        app.update_state(cfg, {
            "review": ReviewDecision(approved=True, values=values),
            "config": {"n": int(n), "seed": 42},
        })
        with st.spinner(f"מייצר {int(n)} טפסים..."):
            final = app.invoke(None, cfg)
        st.session_state["population"] = [
            (p if isinstance(p, Record) else Record(**p)).model_dump()
            for p in final["population"]
        ]
        st.session_state["output_images"] = final["output_images"]
        st.session_state["errors"] = [e.message for e in final.get("errors", [])]
        st.session_state["phase"] = "done"
        st.rerun()


def _done_phase() -> None:
    imgs = st.session_state.get("output_images") or []
    errs = st.session_state.get("errors") or []
    st.success(f"נוצרו {len(imgs)} טפסים.")
    if errs:
        st.warning(f"{len(errs)} כשלו: " + "; ".join(errs[:3]))

    recs = [Record(**p) for p in st.session_state.get("population", [])]
    if recs:
        with st.expander("הערכים שנוצרו (מאומתים)"):
            st.dataframe(records_to_rows(recs), use_container_width=True)

    if imgs:
        st.download_button("הורד הכל (zip)", zip_images(imgs),
                           file_name="forms.zip", mime="application/zip")
        cols = st.columns(3)
        for i, img in enumerate(imgs):
            c = cols[i % 3]
            c.image(img, caption=f"טופס {i + 1}", use_container_width=True)
            c.download_button("הורד", img, file_name=f"form_{i + 1}.png",
                              mime="image/png", key=f"dl_{i}")

    if st.button("התחל מחדש"):
        for k in ("phase", "app", "detected", "page_images", "population",
                  "output_images", "errors", "thread_id"):
            st.session_state.pop(k, None)
        st.rerun()


if __name__ == "__main__":
    main()
main()
