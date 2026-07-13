"""Streamlit UI for the image-edit pipeline (RTL, Hebrew).

Flow: upload form -> detect values -> review/add/pick N -> generate valid variants
-> gpt-image-2 edits the original per variant -> download images.
Run: uv run streamlit run src/doc2tests/ui/app.py
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

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
from doc2tests.orchestrator.batch import process_batch, render_variant
from doc2tests.orchestrator.config import build_extract_provider, build_image_provider
from doc2tests.orchestrator.graph import build_graph
from doc2tests.ui.helpers import records_to_rows, zip_images

load_dotenv()

st.set_page_config(page_title="מחולל טפסים", layout="wide",
                   initial_sidebar_state="collapsed")

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;800&display=swap');

:root{
  --glass: rgba(255,255,255,.045);
  --glass-brd: rgba(255,255,255,.10);
  --accent: #8b5cf6;
  --accent2: #4f46e5;
  --muted: #9aa3c0;
}
html, body, .stApp, [class*="css"]{ font-family:'Heebo',-apple-system,'Segoe UI',sans-serif; }
.stApp{
  direction:rtl; text-align:right; color:#e8eaf2;
  background:
    radial-gradient(1100px 520px at 78% -8%, rgba(124,58,237,.35) 0%, transparent 60%),
    radial-gradient(900px 500px at 12% 8%, rgba(59,130,246,.18) 0%, transparent 55%),
    linear-gradient(160deg,#0a0e1f 0%,#0b1226 55%,#090c1a 100%);
  background-attachment: fixed;
}
[data-testid="stHeader"]{ background:transparent; }
.block-container{ padding-top:2.2rem; max-width:1200px; }

/* ---- RTL: force right-to-left across Streamlit's nested containers ---- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
.block-container, [data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMarkdownContainer"], [data-testid="stHeading"], [data-testid="stExpander"],
[data-testid="stForm"], .stMarkdown, .stCaption{
  direction:rtl!important; text-align:right!important;
}
/* columns flow right-to-left */
[data-testid="stHorizontalBlock"]{ flex-direction:row-reverse; }
/* radio options right-to-left */
[data-testid="stRadio"] > div{ flex-direction:row-reverse; justify-content:flex-start; }
/* inputs / selects / uploader text right-aligned */
input, textarea, [data-baseweb="input"], [data-baseweb="select"],
[data-testid="stFileUploaderDropzone"], [data-testid="stNumberInputContainer"]{
  direction:rtl!important; text-align:right!important;
}
[data-testid="stFileUploaderDropzone"]{ flex-direction:row-reverse; }
/* tables / dataframe RTL */
[data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stDataEditor"]{
  direction:rtl!important;
}

/* headings */
h1{ font-weight:800; letter-spacing:-.02em; font-size:2.5rem; margin-bottom:.2rem; }
h2,h3{ font-weight:600; letter-spacing:-.01em; }
.stCaption, .st-emotion-cache small{ color:var(--muted); }

/* glass panels: expanders + dataframes */
[data-testid="stExpander"]{
  background:var(--glass); border:1px solid var(--glass-brd);
  border-radius:20px; backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
  box-shadow:0 10px 40px rgba(0,0,0,.35); overflow:hidden; margin-bottom:14px;
}
[data-testid="stExpander"] summary{ font-weight:600; padding:.5rem .3rem; }
[data-testid="stDataFrame"], [data-testid="stTable"]{
  border-radius:16px; overflow:hidden; border:1px solid var(--glass-brd);
}

/* inputs / uploader as glass */
[data-testid="stFileUploaderDropzone"],
.stTextInput input, .stNumberInput input, [data-baseweb="select"]>div{
  background:var(--glass)!important; border:1px solid var(--glass-brd)!important;
  border-radius:14px!important; color:#e8eaf2!important;
}
[data-testid="stFileUploaderDropzone"]{ padding:1.4rem; }

/* buttons: purple gradient, rounded, glow */
.stButton>button, .stDownloadButton>button{
  background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);
  color:#fff; border:0; border-radius:14px; font-weight:600; padding:.5rem 1.15rem;
  box-shadow:0 8px 24px rgba(124,58,237,.35); transition:transform .12s, box-shadow .12s;
}
.stButton>button:hover, .stDownloadButton>button:hover{
  transform:translateY(-1px); box-shadow:0 12px 30px rgba(124,58,237,.5);
}

/* radio pills */
[data-testid="stRadio"] label{ color:#cfd4e6; }

/* stepper */
.stepper{ display:flex; gap:10px; margin:8px 0 26px; flex-wrap:wrap; }
.step{
  flex:1; min-width:120px; padding:12px 14px; border-radius:16px;
  background:var(--glass); border:1px solid var(--glass-brd); backdrop-filter:blur(14px);
  color:var(--muted); font-weight:600; font-size:.92rem; text-align:center;
  transition:all .2s;
}
.step.done{ color:#c7f9dd; border-color:rgba(52,211,153,.35); }
.step.active{
  color:#fff; border-color:rgba(139,92,246,.6);
  background:linear-gradient(135deg,rgba(124,58,237,.35),rgba(79,70,229,.25));
  box-shadow:0 8px 26px rgba(124,58,237,.35);
}
.step .n{ opacity:.6; margin-inline-start:6px; }

/* hero card */
.hero{
  background:var(--glass); border:1px solid var(--glass-brd); border-radius:24px;
  backdrop-filter:blur(20px); padding:26px 30px; margin-bottom:22px;
  box-shadow:0 18px 60px rgba(0,0,0,.4);
  background-image:radial-gradient(600px 200px at 85% -40%, rgba(124,58,237,.4), transparent 60%);
}
.hero h1{ margin:0; }
.hero .sub{ color:var(--muted); font-size:1.05rem; margin-top:4px; }

/* metric tiles */
.tiles{ display:flex; gap:16px; flex-wrap:wrap; margin:6px 0 18px; }
.tile{
  flex:1; min-width:150px; padding:18px 20px; border-radius:18px;
  background:var(--glass); border:1px solid var(--glass-brd); backdrop-filter:blur(16px);
  box-shadow:0 10px 34px rgba(0,0,0,.3);
}
.tile .lbl{ color:var(--muted); font-size:.85rem; }
.tile .val{ font-size:1.9rem; font-weight:800; letter-spacing:-.02em; margin-top:2px; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

_STEPS = ["העלאה", "זיהוי ערכים", "סקירה ואישור", "יצירה ומילוי", "הורדה"]


def _hero(title: str, sub: str) -> None:
    st.markdown(f"<div class='hero'><h1>{title}</h1>"
                f"<div class='sub'>{sub}</div></div>", unsafe_allow_html=True)


def _tiles(items: list[tuple[str, str]]) -> None:
    cells = "".join(
        f"<div class='tile'><div class='lbl'>{lbl}</div>"
        f"<div class='val'>{val}</div></div>" for lbl, val in items)
    st.markdown(f"<div class='tiles'>{cells}</div>", unsafe_allow_html=True)


def _stepper(active: int) -> None:
    steps = ""
    for i, name in enumerate(_STEPS):
        cls = "done" if i < active else ("active" if i == active else "")
        steps += f"<div class='step {cls}'>{name}<span class='n'>{i + 1}</span></div>"
    st.markdown(f"<div class='stepper'>{steps}</div>", unsafe_allow_html=True)


def _save_upload(uploaded: Any) -> str:
    suffix = Path(uploaded.name).suffix
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(uploaded.getbuffer())
    return path


def _thread_cfg() -> dict[str, Any]:
    return {"configurable": {"thread_id": st.session_state["thread_id"]}}


def main() -> None:
    _hero("מחולל טפסים", "החלפת ערכים אישיים בתמונת הטופס — נאמן למקור, מאומת, בסקייל")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("חסר OPENAI_API_KEY בקובץ .env")
        return

    mode = st.radio("מצב עבודה", ["מסמך יחיד", "אצווה — הרבה קבצים"], horizontal=True)
    if mode == "מסמך יחיד":
        _single_flow()
    else:
        _batch_flow()

    with st.sidebar.expander("לוגים", expanded=False):
        st.code("\n".join(recent_logs(120)) or "—")


def _single_flow() -> None:
    if "phase" not in st.session_state:
        st.session_state["phase"] = "upload"
    phase = st.session_state["phase"]
    _stepper({"upload": 0, "review": 2, "done": 4}[phase])
    if phase == "upload":
        _upload_phase()
    elif phase == "review":
        _review_phase()
    elif phase == "done":
        _done_phase()


def _upload_phase() -> None:
    uploaded = st.file_uploader("העלה טופס", type=["jpg", "jpeg", "png", "pdf", "docx"])
    if uploaded and st.button("זהה ערכים", type="primary"):
        path = _save_upload(uploaded)
        st.session_state["thread_id"] = uploaded.name
        app = build_graph(build_extract_provider(), build_image_provider())
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
    recs = [Record(**p) for p in st.session_state.get("population", [])]
    fields = len(recs[0].values) if recs else 0
    _tiles([("טפסים שנוצרו", str(len(imgs))),
            ("שדות שהוחלפו", str(fields)),
            ("כשלים", str(len(errs)))])
    if errs:
        st.warning(f"{len(errs)} כשלו: " + "; ".join(errs[:3]))

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


_UPLOAD_TYPES = ["jpg", "jpeg", "png", "pdf", "docx"]


def _batch_flow() -> None:
    st.subheader("אצווה — עיבוד הרבה קבצים בסקייל")
    st.caption("שלב הדאטה (חילוץ + יצירת ערכים מאומתים) זול ורץ על כל הקבצים. "
               "רינדור התמונה יקר — נעשה לפי דרישה, לכל וריאציה בנפרד.")
    files = st.file_uploader("העלה טפסים (אפשר כמה)", type=_UPLOAD_TYPES,
                             accept_multiple_files=True)
    col_a, col_b = st.columns(2)
    n = col_a.number_input("וריאציות לכל קובץ", min_value=1, max_value=50, value=10)
    workers = col_b.number_input("מקביליות (קבצים במקביל)", min_value=1, max_value=16,
                                 value=4)

    if files and st.button("עבד אצווה (חילוץ + יצירת ערכים)", type="primary"):
        paths = [_save_upload(f) for f in files]
        with st.spinner(f"מעבד {len(paths)} קבצים (ללא יצירת תמונות)..."):
            results = process_batch(paths, build_extract_provider(), n=int(n),
                                    max_workers=int(workers))
        st.session_state["batch_results"] = results
        st.session_state["batch_names"] = [f.name for f in files]
        st.session_state["batch_rendered"] = {}
        st.rerun()

    stored = st.session_state.get("batch_results")
    if stored:
        _render_batch_results(stored)


def _render_batch_results(results: list[Any]) -> None:
    names = st.session_state.get("batch_names", [])
    ok = sum(1 for r in results if not r.error)
    st.success(f"עובדו {len(results)} קבצים ({ok} תקינים). ערכים מאומתים מוכנים.")
    rendered: dict[tuple[int, int], bytes] = st.session_state["batch_rendered"]

    for i, doc in enumerate(results):
        name = names[i] if i < len(names) else doc.path
        title = f"📄 {name} — {len(doc.population)} וריאציות"
        if doc.error:
            title += " ⚠️"
        with st.expander(title):
            if doc.error:
                st.error(doc.error)
                continue
            if doc.page_image:
                st.image(doc.page_image, width=280, caption="מקור")
            st.dataframe(records_to_rows(doc.population), use_container_width=True)

            st.caption("רינדור תמונה — קריאה יקרה, לחיצה = תמונה אחת:")
            cols = st.columns(min(len(doc.population), 5) or 1)
            for j in range(len(doc.population)):
                cell = cols[j % len(cols)]
                key = (i, j)
                if key in rendered:
                    cell.image(rendered[key], caption=f"וריאציה {j + 1}")
                    cell.download_button("הורד", rendered[key],
                                         file_name=f"{name}_{j + 1}.png",
                                         mime="image/png", key=f"bdl_{i}_{j}")
                elif cell.button(f"רנדר {j + 1}", key=f"br_{i}_{j}"):
                    with st.spinner("מרנדר תמונה..."):
                        rendered[key] = render_variant(doc, j, build_image_provider())
                    st.rerun()

            done = [rendered[(i, j)] for j in range(len(doc.population))
                    if (i, j) in rendered]
            if done:
                st.download_button(f"הורד את כל שרונדרו ({len(done)}) — zip",
                                   zip_images(done, prefix=name),
                                   file_name=f"{name}_forms.zip",
                                   mime="application/zip", key=f"bzip_{i}")


if __name__ == "__main__":
    main()
