"""Streamlit UI for the image-edit pipeline (RTL, Hebrew).

Flow: upload form -> detect values -> review/add/pick N -> generate valid variants
-> gpt-image-2 edits the original per variant -> download images.
Run: uv run streamlit run src/doc2tests/ui/app.py
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from doc2tests.common.logging import log_marker, logs_since, recent_logs
from doc2tests.contracts.batch import DocumentResult
from doc2tests.contracts.enums import FieldType, SourceKind
from doc2tests.contracts.records import Record
from doc2tests.contracts.state import (
    DetectedValue,
    GraphState,
    InputRef,
    ReviewDecision,
)
from doc2tests.db import repo
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


def _variant_values(doc: DocumentResult, j: int) -> dict[str, str]:
    """Human-readable {label: value} for one generated variant (stored in the DB)."""
    rec = doc.population[j]
    return {d.label: rec.values[d.id].value
            for d in doc.detected if d.id in rec.values}


# --- live status: run heavy work in a thread, stream the REAL stage + elapsed --------
_STATUS_MAP = [
    ("editing image", "יוצר תמונה ב-gpt-image-2"),
    ("edit |", "יוצר תמונה ב-gpt-image-2"),
    ("rasteriz", "ממיר קובץ לתמונה"),
    ("transcribe", "מתעתק כל טקסט מהמסמך"),
    ("structure", "מבין ומבנה שדות"),
    ("understand", "מבין את מהות המסמך"),
    ("detect:", "מסווג ומחליט מה אישי"),
    ("data agent", "כותב ערכי תיאור ריאליסטיים"),
    ("shared into slots", "מקשר ערכים חוזרים"),
    ("generated", "מייצר דאטה מאומת"),
]


def _friendly_status(marker: int) -> str:
    """Latest real pipeline stage (Hebrew) — scanning ONLY lines from THIS run (since
    ``marker``), so stale history from a previous render can't leak in."""
    for line in reversed(logs_since(marker)):
        msg = line.split("|", 1)[-1].strip().lower()
        for key, heb in _STATUS_MAP:
            if key in msg:
                return heb
    return ""


def _run_live(fn: Callable[[], Any], label: str, box: Any) -> Any:
    """Run fn() in a background thread; stream the real stage + elapsed seconds into the
    status box (in the LABEL, so it shows even collapsed). Returns fn()'s value."""
    out: dict[str, Any] = {}
    err: dict[str, BaseException] = {}

    def work() -> None:
        try:
            out["v"] = fn()
        except BaseException as e:  # noqa: BLE001 - surfaced on the main thread below
            err["e"] = e

    marker = log_marker()  # scope status to lines emitted from HERE on
    t = threading.Thread(target=work, daemon=True)
    t.start()
    ph = box.empty()
    t0 = time.time()
    while t.is_alive():
        stage = _friendly_status(marker)
        secs = int(time.time() - t0)
        box.update(label=f"{label}{f' — {stage}' if stage else ''} · {secs} שנ׳")
        ph.markdown(f"🔄 {stage or 'עובד...'}")
        time.sleep(0.4)
    t.join()
    if "e" in err:
        box.update(label=f"{label} — שגיאה", state="error")
        raise err["e"]
    ph.empty()
    return out.get("v")


def _archive_flow() -> None:
    """History: every source original (with its unique id) and the images generated
    from it. Click a generated variant to view/download its image."""
    st.subheader("מאגר — קבצי מקור וכל מה שנוצר מהם")
    if not repo.available():
        st.info("אין חיבור למסד נתונים. הגדר DATABASE_URL (או הרץ ב-docker-compose) "
                "כדי לשמור ולצפות בהיסטוריה.")
        return
    sources = repo.list_sources()
    if not sources:
        st.caption("עדיין לא נשמרו קבצים. עבד מסמך והפק תמונה — הוא ייכנס למאגר עם "
                   "מספר יוניקי, ותחתיו כל מה שנוצר ממנו.")
        return
    _tiles([("קבצי מקור", str(len(sources))),
            ("מסמכים שנוצרו", str(sum(s.n_generated for s in sources)))])
    for src in sources:
        with st.expander(f"#{src.id} · {src.filename} — {src.n_generated} מסמכים שנוצרו"):
            if src.doc_summary:
                st.caption(f"📄 {src.doc_summary}")
            gens = repo.list_generated(src.id)
            if not gens:
                st.caption("אין עדיין תמונות שנוצרו (דאטה בלבד).")
                continue
            labels = [f"וריאציה {g.variant_index + 1}  ·  #{g.id}" for g in gens]
            choice = st.radio("בחר מסמך שנוצר", labels, key=f"arc_{src.id}",
                              index=0, horizontal=True)
            g = gens[labels.index(choice)]
            img = repo.get_image(g.id)
            if img:
                st.image(img, caption=choice, width=460)
                st.download_button("⬇️ הורד", img, mime="image/png",
                                   file_name=f"{src.filename}_{g.variant_index + 1}.png",
                                   key=f"arcdl_{g.id}")
            if g.values:
                with st.expander("הערכים של המסמך הזה"):
                    st.json(g.values)


def main() -> None:
    _hero("מחולל טפסים", "החלפת ערכים אישיים בתמונת הטופס — נאמן למקור, מאומת, בסקייל")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("חסר OPENAI_API_KEY בקובץ .env")
        return

    mode = st.radio("מצב עבודה",
                    ["מסמך יחיד", "אצווה — הרבה קבצים", "מאגר — היסטוריה"],
                    horizontal=True)
    if mode == "מסמך יחיד":
        _single_flow()
    elif mode == "אצווה — הרבה קבצים":
        _batch_flow()
    else:
        _archive_flow()

    with st.sidebar.expander("לוגים (מקצה לקצה)", expanded=False):
        logs = recent_logs(400)
        st.code("\n".join(logs) or "—")
        if logs:
            st.download_button("הורד לוגים", "\n".join(logs),
                               file_name="run.log", mime="text/plain")


def _single_flow() -> None:
    if "phase" not in st.session_state:
        st.session_state["phase"] = "upload"
    phase = st.session_state["phase"]
    _stepper({"upload": 0, "review": 2, "done": 3}[phase])
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
        app = build_graph(build_extract_provider())
        init = GraphState(
            input_ref=InputRef(path=path, kind=SourceKind(detect_kind(path))))
        cfg = _thread_cfg()  # read session_state on the MAIN thread, not in the worker
        box = st.status("מזהה ערכים...", expanded=True)
        _run_live(lambda: app.invoke(init, cfg), "מזהה ערכים", box)
        box.update(label="✓ הזיהוי הושלם", state="complete")
        st.session_state["app"] = app
        snap = app.get_state(cfg)
        st.session_state["detected"] = [d.model_dump() for d in snap.values["detected"]]
        st.session_state["page_images"] = snap.values["page_images"]
        pr = snap.values.get("parse_result")
        st.session_state["doc_summary"] = getattr(pr, "doc_summary", "") if pr else ""
        st.session_state["phase"] = "review"
        st.rerun()


def _review_phase() -> None:
    imgs = st.session_state.get("page_images") or []
    if imgs:
        st.image(imgs[0], caption="הטופס שנקלט", width=380)

    summary = st.session_state.get("doc_summary")
    if summary:
        st.info(f"📄 הבנת המסמך: {summary}")

    st.subheader("ערכים שזוהו — אשר, ערוך, או הוסף")
    st.caption("סמן 'אישי?' לכל ערך שיש להחליף. 'קישור' = ערכים עם אותו קישור מקבלים "
               "ערך זהה (אותה ישות בטופס). הוסף שורות לערכים שלא זוהו.")
    rows = [
        {"label": d["label"], "value": d["value"],
         "field_type": d["field_type"], "אישי?": d["is_personal"],
         "קישור": d.get("slot") or ""}
        for d in st.session_state["detected"]
    ]
    edited = st.data_editor(
        rows, num_rows="dynamic", use_container_width=True,
        column_config={
            "field_type": st.column_config.SelectboxColumn(
                "סוג", options=[t.value for t in FieldType]),
            "אישי?": st.column_config.CheckboxColumn("אישי?"),
            "קישור": st.column_config.TextColumn(
                "קישור", help="ערכים עם אותו קישור יקבלו ערך זהה"),
        },
    )
    n = st.number_input("כמה וריאציות דאטה ליצור?", min_value=1, max_value=50, value=10)
    st.caption("שלב זה מייצר רק את הדאטה (ערכים מאומתים). יצירת התמונה היקרה מתבצעת "
               "אחר כך, לפי דרישה, לכל וריאציה שתבחר.")

    if st.button("צור דאטה (ערכים בלבד)", type="primary"):
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
                slot=(str(r.get("קישור") or "").strip() or None),
            ))
        app = st.session_state["app"]
        cfg = _thread_cfg()
        app.update_state(cfg, {
            "review": ReviewDecision(approved=True, values=values),
            "config": {"n": int(n), "seed": 42},
        })
        box = st.status(f"מייצר דאטה ל-{int(n)} וריאציות (ללא תמונות)...", expanded=True)
        final = _run_live(lambda: app.invoke(None, cfg),
                          f"מייצר דאטה ל-{int(n)} וריאציות", box)
        box.update(label="✓ הדאטה מוכן", state="complete")
        snap = app.get_state(cfg)
        population = [p if isinstance(p, Record) else Record(**p)
                      for p in final["population"]]
        imgs = st.session_state.get("page_images") or []
        summary = st.session_state.get("doc_summary", "")
        name = st.session_state.get("thread_id", "form")
        doc = DocumentResult(
            path=name, detected=snap.values["detected"], population=population,
            page_image=imgs[0] if imgs else None, doc_summary=summary,
        )
        st.session_state["doc_result"] = doc
        # register the source in the archive; images are attached to it on render
        st.session_state["source_id"] = repo.save_source(
            name, doc.page_image, summary)
        st.session_state["single_rendered"] = {}
        st.session_state["phase"] = "done"
        st.rerun()


def _render_many(doc: DocumentResult, indices: list[int],
                 rendered: dict[int, bytes], source_id: int | None) -> None:
    """Render the selected variants one by one, streaming real progress (k/total +
    elapsed). Skips already-rendered ones. Persists each image under its source."""
    todo = [j for j in indices if j not in rendered]
    if not todo:
        st.toast("כל הנבחרים כבר נוצרו")
        return
    box = st.status(f"מרנדר {len(todo)} טפסים...", expanded=True)
    prog = st.progress(0.0)
    provider = build_image_provider()
    for k, j in enumerate(todo):
        img = _run_live(
            partial(render_variant, doc, j, provider),
            f"יוצר טופס {j + 1}  ({k + 1}/{len(todo)})", box)
        rendered[j] = img
        if source_id is not None:
            repo.save_generated(source_id, j, _variant_values(doc, j), img)
        prog.progress((k + 1) / len(todo))
    box.update(label=f"✓ נוצרו {len(todo)} טפסים", state="complete")
    st.rerun()


def _done_phase() -> None:
    """Data is ready and approved. Render an image ONLY on explicit per-variant demand
    (the expensive gpt-image-2 step), never automatically."""
    doc: DocumentResult = st.session_state["doc_result"]
    recs = doc.population
    rendered: dict[int, bytes] = st.session_state.setdefault("single_rendered", {})
    n_personal = len([d for d in doc.detected if d.is_personal])
    _tiles([("וריאציות דאטה", str(len(recs))),
            ("שדות אישיים להחלפה", str(n_personal)),
            ("תמונות שרונדרו", str(len(rendered)))])

    if doc.page_image:
        st.image(doc.page_image, width=340, caption="הטופס המקורי")
    summary = st.session_state.get("doc_summary")
    if summary:
        st.info(f"📄 הבנת המסמך: {summary}")

    st.subheader("טפסים שנוצרו — סמן 'יצירת טופס' ליצירת תמונה")
    st.caption("הטבלה = הדאטה המאומת לכל וריאציה. סמן בעמודה 'יצירת טופס' אילו להפיק, "
               "או 'רנדר הכל'. כל תמונה = קריאה יקרה ל-gpt-image-2 (מתאים גם למאות קבצים).")
    if recs:
        base = records_to_rows(recs)
        value_cols = [k for k in base[0] if k != "#"]
        table = [{
            "יצירת טופס": False,
            "וריאציה": int(str(r["#"])),
            "סטטוס": ("✓ נוצר" if int(str(r["#"])) - 1 in rendered else "ממתין"),
            **{k: r[k] for k in value_cols},
        } for r in base]
        edited = st.data_editor(
            table, use_container_width=True, hide_index=True, key="render_select",
            column_config={
                "יצירת טופס": st.column_config.CheckboxColumn(
                    "יצירת טופס", help="סמן כדי להפיק תמונה לוריאציה זו"),
            },
            disabled=["וריאציה", "סטטוס", *value_cols],
        )
        selected = [int(str(r["וריאציה"])) - 1 for r in edited if r.get("יצירת טופס")]
        c1, c2 = st.columns(2)
        go_sel = c1.button(f"🖼️ רנדר נבחרים ({len(selected)})",
                           disabled=not selected, type="primary")
        go_all = c2.button(f"🖼️ רנדר הכל ({len(recs)})")
        targets = list(range(len(recs))) if go_all else (selected if go_sel else [])
        if targets:
            _render_many(doc, targets, rendered, st.session_state.get("source_id"))

        with st.expander("🔍 אבחון — מה קרה לכל שדה (מקצה לקצה)"):
            st.caption("לכל שדה: התווית, הסוג, אם להחלפה, הקישור (ערכים עם אותו קישור "
                       "מקבלים ערך זהה), הערך המקורי והערך שנוצר.")
            first = recs[0].values
            trace = [{
                "תווית": d.label, "סוג": d.field_type.value,
                "להחלפה?": "כן" if d.is_personal else "לא",
                "קישור": d.slot or "—", "ערך מקורי": d.value,
                "ערך שנוצר": (first[d.id].value if d.id in first else "—"),
            } for d in doc.detected]
            st.dataframe(trace, use_container_width=True)

        done_imgs = [rendered[j] for j in sorted(rendered)]
        if done_imgs:
            st.download_button(f"⬇️ הורד את כל שנוצרו ({len(done_imgs)}) — zip",
                               zip_images(done_imgs), file_name="forms.zip",
                               mime="application/zip")
            gcols = st.columns(min(len(done_imgs), 4) or 1)
            for i, j in enumerate(sorted(rendered)):
                cell = gcols[i % len(gcols)]
                cell.image(rendered[j], caption=f"טופס {j + 1}")
                cell.download_button("הורד", rendered[j], file_name=f"form_{j + 1}.png",
                                     mime="image/png", key=f"sdl_{j}")

    if st.button("התחל מחדש"):
        for k in ("phase", "app", "detected", "page_images", "doc_result",
                  "single_rendered", "thread_id", "source_id", "doc_summary"):
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
        box = st.status(f"מעבד {len(paths)} קבצים (ללא יצירת תמונות)...", expanded=True)
        results = _run_live(
            lambda: process_batch(paths, build_extract_provider(), n=int(n),
                                  max_workers=int(workers)),
            f"מעבד {len(paths)} קבצים", box)
        box.update(label=f"✓ עובדו {len(paths)} קבצים", state="complete")
        st.session_state["batch_results"] = results
        st.session_state["batch_names"] = [f.name for f in files]
        st.session_state["batch_rendered"] = {}
        st.rerun()

    stored = st.session_state.get("batch_results")
    if stored:
        _render_batch_results(stored)


def _render_many_batch(doc: Any, i: int, indices: list[int],
                       rendered: dict[tuple[int, int], bytes], name: str,
                       source_id: int | None) -> None:
    """Render selected variants of one batch file, streaming real progress + persisting."""
    todo = [j for j in indices if (i, j) not in rendered]
    if not todo:
        st.toast("כל הנבחרים כבר נוצרו")
        return
    box = st.status(f"מרנדר {len(todo)} טפסים ({name})...", expanded=True)
    prog = st.progress(0.0)
    provider = build_image_provider()
    for k, j in enumerate(todo):
        img = _run_live(
            partial(render_variant, doc, j, provider),
            f"יוצר טופס {j + 1}  ({k + 1}/{len(todo)})", box)
        rendered[(i, j)] = img
        if source_id is not None:
            repo.save_generated(source_id, j, _variant_values(doc, j), img)
        prog.progress((k + 1) / len(todo))
    box.update(label=f"✓ נוצרו {len(todo)} טפסים", state="complete")
    st.rerun()


def _render_batch_results(results: list[Any]) -> None:
    names = st.session_state.get("batch_names", [])
    ok = sum(1 for r in results if not r.error)
    st.success(f"עובדו {len(results)} קבצים ({ok} תקינים). ערכים מאומתים מוכנים.")
    rendered: dict[tuple[int, int], bytes] = st.session_state["batch_rendered"]
    source_ids: dict[int, int | None] = st.session_state.setdefault("batch_source_ids", {})

    for i, doc in enumerate(results):
        name = names[i] if i < len(names) else doc.path
        title = f"📄 {name} — {len(doc.population)} וריאציות"
        if doc.error:
            title += " ⚠️"
        with st.expander(title):
            if doc.error:
                st.error(doc.error)
                continue
            if i not in source_ids:  # register the source once, for the archive
                source_ids[i] = repo.save_source(name, doc.page_image, doc.doc_summary)
            if doc.page_image:
                st.image(doc.page_image, width=280, caption="מקור")

            st.caption("סמן 'יצירת טופס' לוריאציות להפקה, או 'רנדר הכל'. כל תמונה = "
                       "קריאה יקרה ל-gpt-image-2.")
            base = records_to_rows(doc.population)
            value_cols = [k for k in base[0] if k != "#"] if base else []
            table = [{
                "יצירת טופס": False,
                "וריאציה": int(str(r["#"])),
                "סטטוס": ("✓ נוצר" if (i, int(str(r["#"])) - 1) in rendered else "ממתין"),
                **{k: r[k] for k in value_cols},
            } for r in base]
            edited = st.data_editor(
                table, use_container_width=True, hide_index=True, key=f"bsel_{i}",
                column_config={"יצירת טופס": st.column_config.CheckboxColumn(
                    "יצירת טופס", help="סמן כדי להפיק תמונה")},
                disabled=["וריאציה", "סטטוס", *value_cols])
            selected = [int(str(r["וריאציה"])) - 1 for r in edited if r.get("יצירת טופס")]
            b1, b2 = st.columns(2)
            gs = b1.button(f"🖼️ רנדר נבחרים ({len(selected)})", disabled=not selected,
                           key=f"bgs_{i}", type="primary")
            ga = b2.button(f"🖼️ רנדר הכל ({len(doc.population)})", key=f"bga_{i}")
            targets = (list(range(len(doc.population))) if ga
                       else (selected if gs else []))
            if targets:
                _render_many_batch(doc, i, targets, rendered, name, source_ids.get(i))

            done_js = [j for j in range(len(doc.population)) if (i, j) in rendered]
            if done_js:
                st.download_button(
                    f"⬇️ הורד את כל שנוצרו ({len(done_js)}) — zip",
                    zip_images([rendered[(i, j)] for j in done_js], prefix=name),
                    file_name=f"{name}_forms.zip",
                    mime="application/zip", key=f"bzip_{i}")
                gcols = st.columns(min(len(done_js), 4) or 1)
                for idx, j in enumerate(done_js):
                    cell = gcols[idx % len(gcols)]
                    cell.image(rendered[(i, j)], caption=f"וריאציה {j + 1}")
                    cell.download_button("הורד", rendered[(i, j)],
                                         file_name=f"{name}_{j + 1}.png",
                                         mime="image/png", key=f"bdl_{i}_{j}")


if __name__ == "__main__":
    main()
