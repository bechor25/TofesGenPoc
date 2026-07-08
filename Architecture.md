# מערכת Agentic: מסמך → טמפלייט → אוכלוסיית בדיקות → מילוי המסמך
### מסמך ארכיטקטורה ל‑POC

---

## 1. מה המערכת עושה (הזרימה המלאה)

קלט: **תיקייה או קובץ בודד**, מכל סוג — צילום מהטלפון, PDF, Word, תמונה סרוקה.

```
[קובץ/תיקייה]
      │
      ▼
1. Ingest & Parse      → OCR + הבנת פריסה (טקסט + קואורדינטות)
      │
      ▼
2. De-identify         → זיהוי והסרת PII (Presidio + recognizers ישראליים)
      │
      ▼
3. Templatize          → טמפלייט קנוני (JSON + layout) = מקור האמת
      │
      ▼
4. Schema Extraction   → זיהוי כל השדות + טיפוסים + אילוצים
      │
      ▼
5. Generate Population → אוכלוסיית בדיקות בגודל N (equivalence/boundary/negative)
      │
      ▼
6. Render & Fill       → מילוי הטמפלייט לכל רשומה → DOCX / PDF / HTML
      │
      ▼
[מסמכים ממולאים + dataset + דוח כיסוי]
```

**נקודת מפתח ארכיטקטונית:** הטמפלייט הקנוני (JSON + מיפוי layout) הוא מקור האמת היחיד. DOCX / PDF‑fillable / HTML הם *render targets* מעליו — לא שלושה טמפלייטים נפרדים לתחזוקה.

---

## 2. Agentic או Workflow? (החלטה שחוסכת חודשי refactor)

רוב מה שמתויג "agents" הוא בעצם **DAG workflow** — רצף שלבים דטרמיניסטי עם כמה צמתים של הסקה. הזרימה שלך היא בדיוק כזו: הרוב דטרמיניסטי, וה‑LLM נדרש רק בצמתים ספציפיים (הסקת שדות, אסטרטגיית מקרי קצה, תיאור סמנטי).

**המלצה:** לבנות כ‑**workflow עם צמתי LLM**, לא כ‑swarm חופשי של סוכנים. זה זול יותר, ניתן לניפוי, ודטרמיניסטי היכן שצריך.

| אופציה | מתי לבחור |
|---|---|
| **LangGraph** (מומלץ ל‑POC) | שליטה מלאה ב‑state, checkpointing, human‑in‑the‑loop gate לאישור ה‑de‑identification, observability דרך LangSmith. ~34M הורדות/חודש, deployments ב‑production. |
| **Claude Agent SDK** | אם אתה רוצה להישאר Anthropic‑native; תומך subagents היררכיים (יוני 2026) ו‑MCP first‑class — מתלבש על ה‑`qa-agent` שכבר בנית. |
| **n8n** | לגלו/תזמון ויזואלי בלבד, לא ללב הלוגי — אתה כבר מכיר אותו, שימושי ל‑orchestration קליל של batch. |

לגבי ה‑POC אני ממליץ **LangGraph** בגלל ה‑review gate וה‑state persistence, או Claude Agent SDK אם תרצה המשכיות מלאה עם ה‑stack שלך.

---

## 3. מה קיים מהמדף לעומת מה שצריך לפתח

### שלב 1 — Ingest & Parse (OCR + layout)
**קיים, בשל.** בחירה עיקרית: מקומי (פרטיות — קריטי למסמכים רפואיים) מול ענן (דיוק גבוה יותר).

| כלי | סוג | הערות |
|---|---|---|
| **Docling** (IBM, MIT) | מקומי | PDF/DOCX/PPTX/HTML, ניתוח פריסה + reading order, מחזיר קואורדינטות, יש לו MCP server. ברירת מחדל טובה לפרטיות. |
| **Marker** (Surya) | מקומי | OCR חזק, מומלץ GPU, רישיון GPL. |
| **PyMuPDF** | מקומי | מניפולציה low‑level של PDF + קואורדינטות — נחוץ לשלב המילוי בחזרה. |
| **VLM** (Claude / Gemini vision) | ענן | הכי טוב לכתב יד ולעברית עם הסקה; שקול DPA/BAA למסמכים רפואיים. |
| Azure Document Intelligence | ענן | תמיכה רשמית בעברית, key‑value pairs. |

> **סיכון האיכות העיקרי: כתב יד עברי + RTL.** לפני שבונים מעל — הרם benchmark קטן על דגימות אמיתיות שלך. זה השלב היחיד שבו האיכות לא מובטחת מהמדף.

**המלצה ל‑POC:** Docling מקומי לפריסה + קואורדינטות, ומעליו pass של VLM (Claude vision) לשדות עבריים/כתב יד. שילוב = פרטיות ברירת מחדל + דיוק היכן שצריך.

### שלב 2 — De-identify
**קיים, מצוין להתאמה.** **Microsoft Presidio** (MIT, on‑prem, גרסה 2.2.362 ממרץ 2026):
- Custom recognizers עם **checksum validation** — בדיוק מה שצריך ל‑ת"ז ולמספר רישיון רופא.
- **Image Redactor** (OCR + השחרה ברמת הפיקסל) לצילומים וסריקות.
- זיהוי מבוסס‑LLM דרך **LangExtract + Ollama** (מקומי) — מתלבש על ה‑Ollama שלך.
- רץ כספרייה / Docker / K8s — הדאטה לא יוצא מהפרימטר.

לעברית: כדאי להעריך את **HebSafeHarbor** (פרויקט de‑identification עברי מעל Presidio) — יש לוודא סטטוס תחזוקה עדכני; בכל מקרה DictaBERT/AlephBERT כ‑NER עברי משלימים.

**מה לפתח:** recognizers ישראליים (ת"ז, רישיון רופא, קופת חולים) — כמה עשרות שורות כל אחד, כולל checksum. זה חד‑פעמי ורב‑שימושי.

### שלב 3 — Templatize (טמפלייט קנוני)
**זה הפער הגדול — פיתוח.** לוקחים את פלט הפרסינג + הקואורדינטות + ה‑spans שזוהו כ‑PII, ומייצרים JSON קנוני: לכל שדה — id, label, טיפוס, אילוצים, placeholder, ו‑bounding box. שני מסלולי שחזור:
- **Overlay על המקור** (PyMuPDF): שומרים את הקובץ המקורי כרקע, מאפסים שדות PII, וממלאים טקסט בקואורדינטות → נאמנות ויזואלית 1:1.
- **שחזור מובנה** (HTML/DOCX): בונים מחדש מהסכמה → ניתן לעריכה, פחות pixel‑perfect.

ה‑LLM עוזר כאן להסיק סמנטיקה של שדות; המיפוי והרינדור הם קוד.

### שלב 4 — Schema Extraction
**קל, מבוסס‑LLM.** Claude מקבל את פלט הפרסינג ומחזיר JSON schema: רשימת שדות, טיפוסים, אילוצים ויחסים (תאריך סיום ≥ התחלה, מספר ימים נגזר). ולידציה על הפלט. פיתוח מינימלי.

### שלב 5 — Generate Population (הלב האיכותי)
**frameworks קיימים, הלוגיקה הישראלית + QA — פיתוח.**

| כלי | תפקיד |
|---|---|
| **Faker / Mimesis** | דאטה בסיסי + providers מותאמים (עברית, ערים, קופ"ח) |
| **SDV** (Synthetic Data Vault) | דאטה טבלאי סינתטי ששומר על התפלגויות |
| **LLM** (Claude) | תוכן עברי ריאליסטי והקשרי |
| **Validators ישראליים** | ת"ז עם ספרת ביקורת, פורמט טלפון/תאריך |

מה שהופך את זה ל"איכותי ומתאים" ולא faker אקראי — **תכנון בדיקות**: equivalence classes + boundary values + מקרים שליליים (ת"ז לא תקין, סיום לפני התחלה, תאריך עתידי, שדה חובה חסר, עומס RTL/encoding). זו לוגיקת ה‑strategy agent שלך, לא ספרייה גנרית. פרמטר **N** שולט בגודל האוכלוסייה ובתמהיל המחלקות.

### שלב 6 — Render & Fill
**קיים.** רינדור מהטמפלייט הקנוני ל‑3 פורמטים:

| פורמט | ספרייה |
|---|---|
| **DOCX** | `docxtpl` (placeholders בסגנון Jinja2) |
| **HTML** | Jinja2 |
| **PDF** | HTML→PDF דרך WeasyPrint / Playwright, **או** מילוי AcroForm דרך PyMuPDF / pypdf אם המקור טופס ניתן‑למילוי |

### שלב 7 — Web App
**קיים.** Backend: **FastAPI**. Orchestration: **LangGraph**. Frontend ל‑POC: Streamlit או React פשוט. תור אסינכרוני (Celery/RQ, או BullMQ שאתה מכיר) לעבודת batch. **Review gate** אנושי לפני שלב היצירה — לאישור הטמפלייט המנוקה והסכמה (חשוב לנכונות וגם לבטיחות דאטה רפואי).

---

## 4. סיכום Build vs. Buy

| רכיב | סטטוס | בחירה מומלצת |
|---|---|---|
| פרסינג / OCR | ✅ קיים | Docling + VLM pass |
| מנוע de‑id | ✅ קיים | Presidio (מקומי) |
| frameworks לדאטה סינתטי | ✅ קיים | Faker + SDV |
| רינדור לפורמטים | ✅ קיים | docxtpl + WeasyPrint + PyMuPDF |
| Orchestration | ✅ קיים | LangGraph / Claude Agent SDK |
| Web / API | ✅ קיים | FastAPI (+ Streamlit ל‑POC) |
| **חילוץ טמפלייט קנוני + layout map** | 🔨 פיתוח | הליבה של הפרויקט |
| **Recognizers/validators ישראליים** | 🔨 פיתוח | חד‑פעמי, רב‑שימושי |
| **לוגיקת יצירה QA‑aware** | 🔨 פיתוח | המבדיל האיכותי |
| **רינדור רב‑פורמטי מטמפלייט אחד** | 🔨 פיתוח | glue מעל הספריות |
| **תזמור + UI + review gate** | 🔨 פיתוח | glue |

**המסקנה:** ~60% מהרכיבים קיימים ובשלים. הפיתוח מתרכז בארבעה מקומות: חילוץ הטמפלייט, הכללים הישראליים, לוגיקת הבדיקות, והתזמור. אף אחד מהם אינו מחקרי — הכול הרכבה + הנדסה.

---

## 5. Stack מומלץ ל‑POC (מקומי, חסכוני)

```
Orchestration : LangGraph  (+ LangSmith לtracing)
Parsing       : Docling (מקומי) + Claude vision (שדות עברית/כתב-יד)
De-id         : Presidio + recognizers ישראליים + Ollama (LangExtract)
Schema        : Claude (JSON schema)
Generation    : Faker + providers ישראליים + validators + Claude לתוכן
Render        : docxtpl (DOCX) · WeasyPrint (PDF) · Jinja2 (HTML) · PyMuPDF (overlay/forms)
Backend/API   : FastAPI + Celery/RQ
Frontend      : Streamlit (POC) → React בהמשך
Storage       : filesystem/S3 לפלטים, Postgres למטא-דאטה
```

עלות שולית כמעט אפסית: Docling + Presidio + Ollama רצים מקומית; VLM בענן רק היכן שנדרש. batch כדי לצמצם קריאות.

מבנה ריפו מוצע:
```
doc2tests/
├── orchestrator/      # LangGraph graph + state
├── ingest/            # routing + Docling/VLM
├── deid/              # Presidio + recognizers ישראליים
├── template/          # חילוץ טמפלייט קנוני + layout map
├── schema/            # הסקת schema מבוססת-LLM
├── generate/          # QA strategy + validators + providers
├── render/            # docx/pdf/html renderers
├── api/               # FastAPI + תור
└── ui/                # Streamlit
```

---

## 6. תוכנית POC בשלבים

**Phase 0 — אנכי צר (הוכחת היתכנות):**
סוג מסמך אחד (אישור מחלה), פורמט קלט אחד (PDF או צילום), פלט HTML + DOCX. שרשרת מלאה קובץ→טמפלייט→N רשומות→מסמכים ממולאים. review gate ידני.

**Phase 1 — הרחבה:**
הוספת fillable‑PDF, batch על תיקייה, סוגי מסמכים נוספים, overlay 1:1 עם PyMuPDF.

**Phase 2 — הקשחה:**
benchmark OCR לעברית, מדדי recall ל‑de‑id, observability, אריזה כ‑service.

---

## 7. סיכונים ומיטיגציה

| סיכון | מיטיגציה |
|---|---|
| כתב יד עברי + RTL ב‑OCR | benchmark מוקדם; VLM pass; fallback לתיקון ידני |
| נאמנות ויזואלית 1:1 | מסלול overlay (PyMuPDF) כברירת מחדל; שחזור מובנה כאופציה |
| **recall של de‑id (PII שנפספס)** | review gate אנושי חובה; שילוב regex+checksum+NER+LLM; דאטה רפואי — לא לדלג |
| דיוק ולידטורים ישראליים | בדיקות יחידה מול ת"ז ידועות; ספריית validators משותפת |
| עלות VLM per‑page | מקומי‑תחילה; VLM רק לשדות קשים; batching |

---

### שורה תחתונה
לא קיים מוצר מדף שעושה את כל השרשרת. אבל כל אבן בניין קריטית קיימת, בשלה, וברובה open‑source ומקומית. הפרויקט ריאלי כ‑POC: מתחילים באנכי צר של סוג מסמך אחד, מוכיחים את השרשרת מקצה לקצה, ואז מרחיבים. ה‑POV שכבר בנינו (סכמה + ולידטור ת"ז + מחולל QA‑aware) הוא בדיוק הזרע לשלבים 4–5.