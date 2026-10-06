# AI Study Companion — Architecture & Design Document

> Multimodal AI Hackathon 2026, Track D: Personalized Tutoring & Adaptive Learning

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (Next.js)                        │
│  Upload → Knowledge Map → Tutor Chat → Assessment → Dashboard   │
└────────────────────┬────────────────────────────────────────────┘
                     │ REST / WebSocket
┌────────────────────▼────────────────────────────────────────────┐
│                   FastAPI Backend  (Python 3.11)                 │
│                                                                  │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐  │
│  │  Ingestion   │  │  RAG / Chat   │  │  Assessment Engine   │  │
│  │  Worker      │  │  Service      │  │  (Quiz gen/grading)  │  │
│  └──────┬───────┘  └───────┬───────┘  └──────────┬───────────┘  │
│         │                  │                      │              │
│  ┌──────▼──────────────────▼──────────────────────▼───────────┐  │
│  │              Core Services Layer                            │  │
│  │  LLM/VLM Provider  ·  Embedding Provider  ·  Whisper ASR   │  │
│  └──────┬───────────────────────────────────────┬─────────────┘  │
│         │                                        │               │
│  ┌──────▼────────────┐              ┌────────────▼─────────────┐ │
│  │  ChromaDB          │              │  PostgreSQL (SQLite dev)  │ │
│  │  (vector + BM25)   │              │  Learner model · History  │ │
│  └───────────────────┘              └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | Next.js 14 (App Router) + Tailwind | SSR, file-based routing, easy API proxy |
| PDF Viewer | react-pdf / PDF.js | Page-level deep links |
| Video Player | react-player + custom seek | Timestamp deep links |
| Graph Viz | React Flow | Topic/prerequisite map |
| Backend | FastAPI + Uvicorn | Async, auto-docs, pythonic |
| Job Queue | Celery + Redis (dev: thread pool) | Background ingestion |
| Vector DB | ChromaDB (local) | Free, persistent, hybrid BM25+dense |
| Relational DB | SQLite (dev) → PostgreSQL (prod) | Learner model, history, sources |
| ASR | OpenAI Whisper (local `base` / `small`) | Free, offline, timestamps |
| LLM/VLM | Google Gemini 1.5 Flash (primary) | Free tier, multimodal, long context |
| Embeddings | `text-embedding-004` (Google) | Free tier |
| PDF parse | PyMuPDF (fitz) | Fast, accurate, figure extraction |
| PPTX parse | python-pptx | Slide text + images |
| Eval | RAGAS + custom scripts | Standard RAG eval |
| Containerization | Docker Compose | Single-command startup |

---

## 3. Data Schemas

### 3.1 Source (DB table)

```sql
CREATE TABLE sources (
  id            TEXT PRIMARY KEY,       -- uuid
  student_id    TEXT NOT NULL,
  source_type   TEXT NOT NULL,          -- 'video' | 'pdf' | 'pptx'
  title         TEXT NOT NULL,
  file_path     TEXT,                   -- local storage path
  url           TEXT,                   -- YouTube URL (video only)
  total_pages   INTEGER,               -- pdf/pptx
  duration_sec  REAL,                  -- video
  status        TEXT DEFAULT 'pending', -- pending|processing|ready|error
  error_msg     TEXT,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 KnowledgeUnit (DB table + Chroma document)

```sql
CREATE TABLE knowledge_units (
  unit_id       TEXT PRIMARY KEY,
  source_id     TEXT REFERENCES sources(id),
  source_type   TEXT,                        -- 'video'|'pdf'|'pptx'
  location      TEXT,                        -- "p42" | "s7" | "0:34-1:12"
  text          TEXT NOT NULL,
  modality      TEXT,                        -- 'text'|'image_caption'|'transcript'
  topic_ids     TEXT,                        -- JSON array of topic IDs
  concept_ids   TEXT,                        -- JSON array of concept IDs
  embedding_id  TEXT,                        -- Chroma doc id
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 Topic / Concept / Prerequisite

```sql
CREATE TABLE topics (
  id           TEXT PRIMARY KEY,
  source_id    TEXT REFERENCES sources(id),
  student_id   TEXT,
  name         TEXT,
  parent_id    TEXT REFERENCES topics(id),   -- NULL = top-level
  level        INTEGER DEFAULT 0             -- 0=topic, 1=subtopic, 2=concept
);

CREATE TABLE prerequisites (
  from_id   TEXT,   -- topic / concept id
  to_id     TEXT,   -- depends on
  PRIMARY KEY (from_id, to_id)
);
```

### 3.4 Learner Model

```sql
CREATE TABLE students (
  id           TEXT PRIMARY KEY,
  name         TEXT,
  exam_date    DATE,
  goals        TEXT,
  created_at   DATETIME
);

CREATE TABLE concept_mastery (
  student_id      TEXT,
  concept_id      TEXT,
  mastery_prob    REAL DEFAULT 0.3,   -- BKT posterior P(mastery)
  uncertainty     REAL DEFAULT 0.5,   -- variance / confidence
  last_reviewed   DATETIME,
  next_review     DATETIME,           -- spaced repetition due date
  slip            REAL DEFAULT 0.1,   -- BKT slip rate
  guess           REAL DEFAULT 0.25,  -- BKT guess rate
  PRIMARY KEY (student_id, concept_id)
);

CREATE TABLE interaction_history (
  id            TEXT PRIMARY KEY,
  student_id    TEXT,
  session_id    TEXT,
  type          TEXT,     -- 'quiz_answer'|'chat'|'diagnostic'
  concept_id    TEXT,
  correct       INTEGER,  -- 1/0/NULL
  question_text TEXT,
  answer_text   TEXT,
  source_units  TEXT,     -- JSON array of unit_ids cited
  ts            DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE questions (
  id            TEXT PRIMARY KEY,
  student_id    TEXT,
  topic_id      TEXT,
  concept_id    TEXT,
  source_unit   TEXT,
  location      TEXT,
  qtype         TEXT,     -- 'mcq'|'short'|'numerical'
  difficulty    INTEGER,  -- 1-5
  stem          TEXT,
  choices       TEXT,     -- JSON (MCQ only)
  answer        TEXT,
  explanation   TEXT,
  verified      INTEGER DEFAULT 0,
  embedding_id  TEXT,
  created_at    DATETIME
);
```

---

## 4. API Endpoints

### Ingestion
```
POST   /api/ingest/upload              # multipart: file + student_id
POST   /api/ingest/youtube             # body: {url, student_id}
GET    /api/ingest/status/{source_id}  # SSE stream of progress
GET    /api/sources                    # list sources for student
DELETE /api/sources/{source_id}        # remove source + units
```

### Knowledge Base
```
GET    /api/knowledge/topics           # topic hierarchy for student
GET    /api/knowledge/graph            # prerequisite graph (nodes+edges)
GET    /api/knowledge/search           # ?q=&topic_id=&source_id=
GET    /api/knowledge/unit/{unit_id}   # single unit details
```

### Tutor Chat
```
POST   /api/chat                       # body: {student_id, message, session_id}
GET    /api/chat/history/{session_id}  # all turns
GET    /api/chat/sessions              # list sessions for student
```

### Assessment
```
POST   /api/assessment/generate        # {student_id, scope, n_questions, qtype}
POST   /api/assessment/submit          # {assessment_id, answers[]}
GET    /api/assessment/{id}/report     # post-assessment report
GET    /api/assessment/history         # all past assessments
```

### Learner Model
```
GET    /api/learner/{student_id}/model       # full mastery state
GET    /api/learner/{student_id}/schedule    # next review items
GET    /api/learner/{student_id}/weak-areas  # sorted weak concepts
POST   /api/learner/onboard                  # diagnostic intake
```

### Eval (internal)
```
POST   /api/eval/run                   # trigger eval suite (async)
GET    /api/eval/results               # latest eval results JSON
```

---

## 5. Folder Structure

```
studycompanion/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── config.py                # settings from .env
│   │   ├── database.py              # SQLAlchemy setup
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── source.py
│   │   │   ├── knowledge.py
│   │   │   ├── learner.py
│   │   │   └── assessment.py
│   │   ├── routers/
│   │   │   ├── ingest.py
│   │   │   ├── knowledge.py
│   │   │   ├── chat.py
│   │   │   ├── assessment.py
│   │   │   └── learner.py
│   │   ├── services/
│   │   │   ├── ingestion/
│   │   │   │   ├── pipeline.py      # orchestrator
│   │   │   │   ├── video.py         # Whisper + keyframe
│   │   │   │   ├── pdf_parser.py    # PyMuPDF + figure captions
│   │   │   │   └── pptx_parser.py   # python-pptx + figure captions
│   │   │   ├── knowledge/
│   │   │   │   ├── chunker.py       # sliding window chunking
│   │   │   │   ├── topic_extractor.py # LLM-based hierarchy
│   │   │   │   ├── vector_store.py  # ChromaDB wrapper (hybrid)
│   │   │   │   └── prerequisite.py  # graph builder + cycle check
│   │   │   ├── chat/
│   │   │   │   ├── rag.py           # retrieval + rerank pipeline
│   │   │   │   ├── grounding.py     # relevance gate
│   │   │   │   └── tutor.py         # prompt assembly + LLM call
│   │   │   ├── assessment/
│   │   │   │   ├── generator.py     # question generation
│   │   │   │   ├── verifier.py      # cross-model + sympy check
│   │   │   │   ├── dedup.py         # embedding dedup
│   │   │   │   └── adaptive.py      # ZPD-based item selection
│   │   │   ├── learner/
│   │   │   │   ├── bkt.py           # Bayesian Knowledge Tracing
│   │   │   │   ├── forgetting.py    # Ebbinghaus / SM2 spaced rep
│   │   │   │   └── model.py         # learner state manager
│   │   │   └── llm/
│   │   │       ├── provider.py      # unified LLM/VLM interface
│   │   │       └── embedder.py      # unified embedding interface
│   │   └── utils/
│   │       ├── id_gen.py
│   │       ├── citation.py          # deep-link formatter
│   │       └── cycle_detect.py      # topological sort / DFS
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx             # Landing / upload
│   │   │   ├── knowledge/page.tsx   # Knowledge map
│   │   │   ├── chat/page.tsx        # Tutor chat
│   │   │   ├── assessment/page.tsx  # Assessment builder/runner
│   │   │   └── dashboard/page.tsx   # Mastery dashboard
│   │   ├── components/
│   │   │   ├── SourceViewer/        # PDF, video, slide viewers
│   │   │   ├── CitationPanel/       # side panel
│   │   │   ├── KnowledgeGraph/      # React Flow graph
│   │   │   ├── MasteryHeatmap/      # mastery heatmap
│   │   │   ├── QuizRunner/          # assessment UI
│   │   │   └── ui/                  # design system primitives
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── types/
│   ├── public/
│   ├── Dockerfile
│   ├── next.config.js
│   └── package.json
├── eval/
│   ├── test_set.json               # ≥50 gold Q&A items
│   ├── run_eval.py                 # single-command eval runner
│   ├── simulate_students.py        # 3+ student profiles
│   ├── results/                    # output JSON + charts
│   └── README.md
├── data/                           # uploaded files (gitignored)
├── chroma_db/                      # vector store (gitignored)
├── docs/
│   ├── ARCHITECTURE.md             # this file
│   ├── grounding_method.md
│   ├── learner_model.md
│   └── design_decisions.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── DEMO_SCRIPT.md
```

---

## 6. Ingestion Pipeline (Phase 1)

```
Input File/URL
     │
     ▼
┌─────────────┐
│  Detect     │  video | pdf | pptx
│  Type       │
└──────┬──────┘
       │
   ┌───┴──────────────────────────────────────┐
   │                                          │
 video                                    pdf / pptx
   │                                          │
   ▼                                          ▼
Whisper ASR                           PyMuPDF / python-pptx
(timestamped transcript)              (text per page/slide)
   │                                          │
keyframe extraction                   figure extraction
(ffmpeg, every N sec)                 (images per page)
   │                                          │
VLM caption each frame                VLM caption each figure
   │                                          │
   └──────────────┬───────────────────────────┘
                  │
            ┌─────▼──────┐
            │  Chunking  │  sliding window, ~400 tokens,
            │            │  overlap 50 tokens, respect
            │            │  sentence/paragraph boundaries
            └─────┬──────┘
                  │
         LLM: extract topics, concepts, tags
                  │
         embed chunks → ChromaDB
                  │
         LLM: build prerequisite graph
                  │
         cycle detection + topological sort
                  │
         persist all to SQLite
```

---

## 7. RAG + Grounding Pipeline (Phase 2)

```
User Query
    │
    ▼
Embed query  →  ChromaDB dense search (top-K=20)
                +  BM25 sparse search (top-K=20)
                    │
                 Reciprocal Rank Fusion (RRF) → top-K=10
                    │
             Cross-encoder reranker (top-5)
                    │
         Relevance gate: max_score >= threshold?
         ├── YES → grounded answer with citations
         └── NO  → "not covered" refusal
                   + optional outside-knowledge answer (clearly labeled)
                    │
         Tutor prompt:
           - learner mastery state (weak concepts → deeper explanation)
           - retrieved units with locations
           - format citations as [1], [2], ...
                    │
         LLM response
                    │
         Parse citations → build deep-link map
                    │
         Return: {answer, citations: [{unit_id, location, snippet}]}
```

---

## 8. Learner Model (Phase 3)

### Bayesian Knowledge Tracing (BKT)

Per-concept parameters:
- `P(L₀)` = initial mastery probability (prior, from diagnostic)
- `P(T)` = transit probability (learn rate, fixed default 0.1)
- `P(S)` = slip probability (student-specific, 0.05–0.2)
- `P(G)` = guess probability (student-specific, 0.15–0.35)

Update after each answer:
```
P(Lₙ | correct) = P(Lₙ₋₁)(1-S) / [P(Lₙ₋₁)(1-S) + (1-P(Lₙ₋₁))G]
P(Lₙ | wrong)   = P(Lₙ₋₁)S     / [P(Lₙ₋₁)S + (1-P(Lₙ₋₁))(1-G)]
P(Lₙ₊₁)         = P(Lₙ) + (1-P(Lₙ)) * P(T)
```

### Forgetting Curve (SM2 / Ebbinghaus)

- Stability `S` increases after each successful recall.
- `next_review = now + S * interval_factor`
- Items due appear in `/api/learner/{id}/schedule`.

### Zone of Proximal Development (ZPD) Item Selection

- Compute `zpd_score = (1 - mastery) * (1 - uncertainty)`.
- Target items in range `mastery ∈ [0.35, 0.75]` (not too easy, not too hard).
- Difficulty ladder: ramp difficulty as mastery rises.

---

## 9. Assessment Engine (Phase 3)

```
Scope selection (topics, sources, page ranges)
    │
Fetch relevant knowledge units
    │
For each question slot:
    │
    ├── Select concept via adaptive/ZPD
    ├── Select unit(s) for context
    ├── Generate question (LLM) with qtype + difficulty
    ├── Verify:
    │     MCQ: cross-check answer with second LLM call
    │     Numerical: execute with sympy / Python eval
    │     Short: rubric check
    ├── Dedup: cosine similarity vs. prior questions ≥ 0.85 → regenerate
    └── Tag: topic_id, concept_id, source_location, difficulty
    │
Assemble assessment object
    │
On submission: grade → update learner model → generate report
```

---

## 10. Evaluation Design (Phase 5)

### RAGAS Metrics
- **Faithfulness**: fraction of answer claims supported by retrieved context.
- **Answer Relevancy**: how well answer addresses the question.
- **Context Precision**: fraction of retrieved chunks actually useful.
- **Context Recall**: fraction of relevant information retrieved.

### Refusal Eval
- 20 on-material questions + 20 off-material questions (out of 50+ set).
- Refusal precision = TP_refusal / (TP_refusal + FP_refusal).
- Refusal recall = TP_refusal / total off-material.

### Personalization Eval
- 3 simulated student profiles:
  - **Alice** (strong, low slip/guess): slip=0.05, guess=0.15, P(L₀)=0.6
  - **Bob** (average): slip=0.10, guess=0.25, P(L₀)=0.3
  - **Carol** (weak, high guess): slip=0.20, guess=0.35, P(L₀)=0.1
- 5 simulated sessions each.
- Compare: adaptive (ZPD) vs. random selection baseline.
- Metrics: mastery gain after each session, question repetition rate.
- Output: `eval/results/personalization.json` + `mastery_gain_plot.png`.

---

## 11. Milestones

| Phase | What | Key Acceptance Checks |
|---|---|---|
| **1** | Ingestion + KB + citation deep-links | All units have location; clicking citation opens viewer at exact spot |
| **2** | Grounded chat + refusal | Off-material query refused; answer cites sources; inline links work |
| **3** | Learner model + assessment | Mastery updates after quiz; no dupe questions; all questions verified & tagged |
| **4** | Dashboard + UI polish | All 5 pages work; heatmap visible; schedule shown |
| **5** | Eval suite | `python eval/run_eval.py` → JSON + charts in `/eval/results/` |
| **6** | Optional features + docs | Course flow map; README complete; Docker works |

---

## 12. Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Vector DB | ChromaDB (local) | Zero-infra, persistent, free; swap to Qdrant for scale |
| LLM | Gemini 1.5 Flash | 1M context, free tier, multimodal (images in prompts) |
| ASR | Whisper `small` | Best free offline option; timestamps with `word_timestamps=True` |
| Chunking | Sliding window 400 tok / 50 overlap | Empirically best for RAG recall on mixed content |
| BKT over IRT | BKT | Simpler, interpretable, well-studied in tutoring systems; IRT needs more data |
| SQLite first | SQLite → PostgreSQL | Easier local dev, same SQLAlchemy ORM |
| Citation format | `[N]` inline → side panel | Clean UX, consistent with academic norms |
| Refusal gate | cosine distance threshold | Tunable, language-independent |
