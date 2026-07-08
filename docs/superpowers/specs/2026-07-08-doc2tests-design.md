# doc2tests — מסמך → טמפלייט קנוני → אוכלוסיית בדיקות → מילוי

**מסמך עיצוב (spec) · POC · 2026-07-08**

מסמך מקור: [Architecture.md](../../../Architecture.md)

---

## 1. מטרה והיקף

מערכת שלוקחת מסמך ישראלי כלשהו (צילום/PDF/סריקה), מחלצת ממנו **טמפלייט קנוני גנרי** (מקור אמת יחיד), ומייצרת ממנו **אוכלוסיית בדיקות** בגודל N — מסמכים ממולאים + dataset + דוח כיסוי.

**היקף מוסכם:**
- **גנרי** — לא מקודד לסוג מסמך יחיד. הטמפלייט נגזר מהמסמך, לא מהנחות.
- שני מסמכי דמה אמיתיים משמשים fixtures ומגדירים את טווח הקושי:
  - **מסמך 1** — טופס בנק בכתב יד ("בקשה להעברת תעודת זכאות", מזרחי טפחות). כתב יד עברי RTL, שני מבקשים עם ת"ז, תאריכי חוזה/כניסה, כתובת, מס' סניף, חתימות. **מקרה OCR קשה.**
  - **מסמך 2** — מכתב מודפס (רשות המסים, "הודעה על קליטת הצהרת הרוכש"). טקסט מכונה: גוש/חלקה, מס' שומה, תאריך, שמות מוכר/רוכש, ברקוד. **מקרה OCR קל.**
- **אין חשש פרטיות ב-POC** — זו הוכחת יכולת. VLM בענן מותר.

**תובנת מפתח:** ה-spans שמזוהים כ-PII/ערכי-טופס הם **בדיוק** השדות המשתנים למילוי. שלב ה-de-id איננו רק פרטיות — הוא מנגנון זיהוי-השדות שמפריד תבנית קבועה מערכים משתנים.

---

## 2. החלטת מודלים (best-fit)

מודלים זמינים: **מקומי (Ollama, Mac 32GB M5)** או **OpenAI API key**. אין Claude API.

הצומת הקריטי בכל המערכת = חילוץ **כתב-יד עברי RTL** (מסמך 1). זה הלֶבֶר שקובע אם ה-POC עובד. VLM מקומי על 32GB לא עומד בעברית כתב-יד; OpenAI vision כן.

**החלטה:** OpenAI vision = ברירת מחדל לצומת החילוץ. Ollama מקומי = pluggable. הכל מאחורי **Provider abstraction** — החלפה בקונפיג בלי לגעת בלוגיקה.

| צומת | מודל ברירת מחדל | נימוק |
|---|---|---|
| Vision extract (F1) | **OpenAI vision** | כתב-יד עברי, קריטי לאיכות |
| Schema infer (F4) | OpenAI / Ollama (config) | reasoning על טקסט מחולץ |
| Population content (F5) | **Ollama מקומי** bulk | N רשומות, חיסכון עלות; OpenAI לאיכות |
| Validators (X2) | **קוד טהור** | נכונות non-negotiable, בלי מודל |

מזהה מודל מדויק (למשל `gpt-4o`) נשמר ב-config, לא מקודד. מאמתים את הדגם העדכני ביותר בזמן המימוש.

---

## 3. הפיצרים הנדרשים

| # | פיצר | תיאור | סטטוס |
|---|---|---|---|
| **F1** | Ingest & Parse | routing קלט (JPEG/PDF/PNG/DOCX) → OpenAI vision → טקסט + layout blocks + bbox | glue מעל VLM |
| **F2** | Field Detection / De-id | spans משתנים = שדות. Presidio + recognizers ישראליים מאמתים/מעשירים | 🔨 ליבה |
| **F3** | Canonical Template | JSON קנוני = מקור אמת. לכל שדה: id, label, type, constraints, placeholder, bbox | 🔨 ליבה |
| **F4** | Schema Extraction | טיפוסים + אילוצים + יחסים (סיום≥התחלה), ולידציה על הפלט | 🔨 LLM-קל |
| **F5** | QA-aware Generation | N רשומות: equivalence + boundary + negative. providers ישראליים + validators + LLM | 🔨 המבדיל |
| **F6** | Render & Fill | טמפלייט → HTML (Jinja2) + DOCX (docxtpl). Overlay 1:1 (PyMuPDF) = Phase 1 | glue |
| **F7** | Orchestrator + Review Gate | LangGraph: state, checkpointing, human review gate. FastAPI + Streamlit UI | 🔨 glue |
| **X1** | Provider abstraction | ממשק LLM/VLM אחד, backends OpenAI + Ollama, config per-node | 🔨 best-practice |
| **X2** | Israeli validators lib | ת"ז (ספרת ביקורת), גוש/חלקה, תאריך, טלפון, סניף — חד-פעמי רב-שימושי | 🔨 |
| **X3** | Coverage report | מטריצת field × class → count, כללים שהופעלו, פערים | 🔨 |

---

## 4. חוזה הדאטה — הטמפלייט הקנוני

מקור האמת היחיד. DOCX/PDF/HTML הם render targets מעליו.

```jsonc
// canonical_template.json
{
  "template_id": "uuid",
  "doc_type": "generic-inferred-label",       // נגזר, לא מקודד
  "language": "he", "direction": "rtl",
  "source": { "kind": "image|pdf", "pages": 1, "render_strategy": "reconstruct|overlay" },
  "layout_blocks": [ { "id": "...", "kind": "heading|paragraph|table|field", "bbox": {}, "page": 1 } ],
  "fields": [
    {
      "id": "primary_applicant_id",           // slug יציב
      "label": "מספר זהות (מבקש ראשי)",        // human RTL
      "type": "israeli_id",                   // enum טיפוסים סמנטיים
      "value_kind": "handwritten|printed",    // אות איכות מ-F1
      "pii": true, "pii_type": "IL_ID",
      "constraints": { "required": true, "checksum": "israeli_id", "length": 9 },
      "placeholder": "{{ primary_applicant_id }}",   // Jinja2 token
      "bbox": { "page": 1, "x": 0.62, "y": 0.34, "w": 0.15, "h": 0.03 }  // יחסי; null אם אין
    }
  ],
  "relations": [
    { "kind": "order", "op": "<=", "left": "contract_date", "right": "entry_date" },
    { "kind": "derived", "field": "days_between", "from": ["contract_date", "entry_date"] }
  ]
}
```

**טיפוסים סמנטיים (type enum):**
`hebrew_name · israeli_id · date · gush_helka · assessment_number · bank_branch · address · phone · currency · enum · free_text`.
כל טיפוס → provider ליצירה (F5) + validator לנכונות (X2).

**אימות גנריות — אותה סכמה, שני מסמכים:**
- מסמך 1 → `primary_applicant_name` (hebrew_name/handwritten), `primary_applicant_id`=318885684, `secondary_applicant_id`=318444973, `contract_sign_date`, `entry_date`, `apartment_address`, `target_branch`=420. Relation: `contract_sign_date <= entry_date`.
- מסמך 2 → `gush`=009007, `helka`=0012, `assessment_number`=119128627, `declaration_date`, `seller_name`, `buyer_name`.

---

## 5. אורקסטרציה — LangGraph

### צמתים וזרימה
```
ingest_parse (F1) → detect_fields (F2) → build_template (F3) → extract_schema (F4)
   → ⏸ review_gate (interrupt, human approve/edit)
        approved → generate_population (F5) → render_fill (F6) → coverage_report (X3) → END
        rejected → build_template (עם edits) | END
```

### State (ערוץ יחיד, Pydantic)
```python
class GraphState(BaseModel):
    input_ref: InputRef                    # path/bytes + kind
    parse_result: ParseResult | None       # F1
    detected_fields: list[DetectedField]   # F2
    template: CanonicalTemplate | None     # F3
    schema: FieldSchema | None             # F4
    review: ReviewDecision | None          # gate: approved/edits
    population: list[Record]               # F5
    coverage: CoverageReport | None        # X3
    outputs: list[RenderedDoc]             # F6
    config: RunConfig                      # N, providers, formats
    errors: list[StageError]
```

### best-practices מפתח
- **checkpointer** (SqliteSaver) → resume אחרי crash + review gate עמיד.
- **interrupt()** ב-review_gate → LangGraph עוצר; UI מציג טמפלייט מנוקה; אדם מאשר/עורך; `Command(resume=...)` ממשיך.
- כל צומת = פונקציה טהורה `State → partial State`, בלי side-effects מוסתרים, testable בבידוד.
- conditional edge אחרי הגייט: approved→generate, rejected→build_template/END.

---

## 6. F5 — QA-aware Generation (המבדיל האיכותי)

אוכלוסיית בדיקות בגודל N. כל רשומה מתויגת: מחלקה + validity צפוי + הכלל שהיא בודקת. Suite של בדיקות, לא דאטה אקראי.

**3 מחלקות (per field-type):**

| מחלקה | מייצר | דוגמה (israeli_id) | דוגמה (relation תאריכים) |
|---|---|---|---|
| Equivalence | ערכים חוקיים ריאליסטיים | ת"ז תקינה + checksum | entry ≥ contract |
| Boundary | קצוות: min/max, אורך, תאריך=תאריך, leap-year, אופציונלי-ריק | 9 ספרות בדיוק, אפסים מובילים | entry = contract |
| Negative | הפרה מכוונת | checksum שגוי, 8 ספרות | entry < contract |

**פייפליין ליצירת שדה:**
```
1. Provider דטרמיניסטי → Faker + providers ישראליים (שם עברי, עיר, קופ"ח)
2. Validator          → מבטיח תקינות (equiv/boundary) או מפר במכוון (negative)
3. LLM (Ollama bulk / OpenAI quality) → תוכן עברי ריאליסטי הקשרי
4. Relation solver    → מספק/מפר יחסים לפי מחלקת הרשומה
```

**Strategy object per type:**
```python
class FieldStrategy(Protocol):
    def equivalence(self) -> Value: ...
    def boundary(self) -> Value: ...
    def negative(self) -> list[Value]: ...
```

**בקרת N + תמהיל (config):** `N=100, mix={equivalence:0.6, boundary:0.25, negative:0.15}` — ניתן-כוונון.

**stress עברי/RTL (מחלקת boundary/negative ייעודית):** ספרות LTR בתוך RTL, ניקוד, מחרוזות ארוכות, encoding — מה ששובר renderers.

**X3 Coverage report:** מטריצת `field × class → count`, כללים שהופעלו, פערים לא-מכוסים.

---

## 7. F6 — Render & Fill

```
canonical_template + record ──┬── Jinja2  → HTML
                              ├── docxtpl → DOCX
                              └── PyMuPDF → overlay 1:1 (Phase 1)
```
- **Phase 0:** HTML + DOCX (reconstruct מהסכמה).
- **Phase 1:** overlay 1:1 על תמונת המקור (JPEG → compositing בקואורדינטות bbox).

---

## 8. מבנה ריפו

```
doc2tests/
├── pyproject.toml            # uv/poetry, ruff, mypy, pytest
├── .env.example              # OPENAI_API_KEY, OLLAMA_HOST
├── src/doc2tests/
│   ├── contracts/            # Pydantic: CanonicalTemplate, GraphState, Record — מקור אמת אחד
│   ├── providers/            # X1: LLMProvider iface + openai/ollama backends + per-node config
│   ├── ingest/               # F1
│   ├── deid/                 # F2 + recognizers ישראליים
│   ├── template/             # F3
│   ├── schema/               # F4
│   ├── generate/             # F5: strategies + providers + relation solver
│   ├── validators/           # X2: israeli_id, gush_helka, date, phone, branch (קוד טהור)
│   ├── render/               # F6
│   ├── coverage/             # X3
│   ├── orchestrator/         # LangGraph graph + nodes + checkpointer
│   ├── api/                  # FastAPI + review-gate endpoints
│   └── ui/                   # Streamlit
├── tests/                    # pytest: unit per module + integration e2e
│   └── fixtures/             # 2 התמונות + expected outputs
└── docs/superpowers/specs/
```

---

## 9. Best-practices מאוכפים

- **contracts/** = Pydantic מקור-אמת. מודולים מדברים דרך המודלים, לא dict-ים.
- **TDD** (superpowers): טסט לפני קוד לכל validator / strategy / node.
- **Provider abstraction** → אפס hardcode של ספק; החלפה ל-Ollama בקונפיג.
- צמתים טהורים `State → partial State`, testable בבידוד.
- `ruff` + `mypy --strict` + `pytest`, CI-ready.
- **Determinism**: seed ל-Faker/strategies → אוכלוסייה משוחזרת.
- `.env` למפתחות, בלי סודות בקוד.
- **2 הדגמים = fixtures** → e2e test אמיתי מהיום הראשון.

---

## 10. תוכנית Phases

| Phase | תוכן |
|---|---|
| **Phase 0** | שרשרת מלאה על **מסמך 2** (מודפס, קל) → HTML+DOCX + N רשומות + coverage. review gate ידני. מוכיח שרשרת מקצה-לקצה. |
| **Phase 1** | **מסמך 1** (כתב-יד) + overlay 1:1 PyMuPDF + batch על תיקייה. |
| **Phase 2** | benchmark OCR עברי, recall de-id, observability (LangSmith), אריזה כ-service. |

---

## 11. סיכונים ומיטיגציה

| סיכון | מיטיגציה |
|---|---|
| כתב יד עברי + RTL (מסמך 1) | OpenAI vision; מסמך 2 קודם ב-Phase 0; fallback לתיקון ידני דרך review gate |
| דיוק bbox מ-VLM | reconstruct ב-Phase 0 (לא תלוי bbox מדויק); overlay רק Phase 1 |
| נכונות validators ישראליים | unit tests מול ת"ז ידועות; ספריית validators משותפת (X2) |
| recall של זיהוי שדות | review gate אנושי חובה; שילוב VLM + Presidio + recognizers |
| עלות OpenAI per-page | Ollama לתוכן bulk; batching; VLM רק לחילוץ |

---

## 12. קריטריוני הצלחה (POC)

1. מסמך 2 עובר שרשרת מלאה → טמפלייט קנוני תקין + N מסמכים ממולאים (HTML+DOCX) + דוח כיסוי.
2. אותה סכמה חולצת גם ממסמך 1 (ולו חלקית) — מוכיח גנריות.
3. אוכלוסייה מכילה את 3 המחלקות עם תיוג validity נכון; validators ישראליים עוברים unit tests.
4. review gate עוצר, מציג, ומאפשר אישור/עריכה לפני יצירה.
5. החלפת provider OpenAI↔Ollama דרך config בלבד.
