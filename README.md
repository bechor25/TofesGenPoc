# doc2tests

מסמך ישראלי (צילום/סריקה/PDF) → **טמפלייט קנוני** → **אוכלוסיית בדיקות QA-aware** → מסמכים ממולאים (HTML/DOCX) + דוח כיסוי.

Pipeline גנרי (לא מקודד לסוג מסמך), מתוזמר ב-LangGraph עם שער-סקירה אנושי.

## הרצה מהירה

```bash
uv sync --extra dev
cp .env.example .env            # ערוך: הכנס OPENAI_API_KEY אמיתי
```

### UI (מקצה לקצה)
```bash
uv run streamlit run src/doc2tests/ui/app.py
# → http://localhost:8501
```
העלה מסמך → "חלץ טמפלייט" → סקור/ערוך שדות → "אשר וייצר" → הורד מסמכים + דוח כיסוי.

### API
```bash
uv run uvicorn doc2tests.api.main:app --reload
# POST /runs (multipart: file,n,formats)  →  {thread_id, fields...}
# POST /runs/{thread_id}/approve (json: edits)  →  {population_size, coverage, outputs}
```

## הזרימה (F1→F6)
```
ingest_parse(F1) → detect_fields(F2) → build_template(F3) → extract_schema(F4)
   → ⏸ review_gate (interrupt: אישור/עריכה) → generate_population(F5) → coverage(X3) → render_fill(F6)
```

## מודלים
- **Vision (חילוץ):** OpenAI (`OPENAI_VISION_MODEL`, ברירת מחדל `gpt-4o`) — כתב-יד עברי RTL.
- **Provider abstraction:** OpenAI / Ollama, החלפה בקונפיג ([config.py](src/doc2tests/orchestrator/config.py)).

## מבנה
| מודול | תפקיד |
|---|---|
| `contracts/` | מודלי Pydantic — הטמפלייט הקנוני + state (מקור אמת) |
| `providers/` | LLMProvider iface + OpenAI/Ollama |
| `validators/` | ת"ז(checksum), תאריך, גוש/חלקה, טלפון, סניף |
| `ingest/ deid/ template/ schema/` | F1–F4 חילוץ |
| `generate/ coverage/` | F5 אוכלוסייה QA-aware + X3 כיסוי |
| `render/` | F6 HTML(Jinja2) + DOCX(python-docx) |
| `orchestrator/` | LangGraph graph + review gate |
| `api/ ui/` | FastAPI + Streamlit |

## פיתוח
```bash
uv run pytest                                        # כולל live (אם יש key)
uv run pytest --ignore=tests/extraction/test_live_openai.py --ignore=tests/orchestrator/test_live_e2e.py
uv run ruff check src tests
uv run mypy
```

תיעוד עיצוב: [docs/superpowers/specs/](docs/superpowers/specs/) · תוכניות: [docs/superpowers/plans/](docs/superpowers/plans/)
