# StudyCompanion AI

> **Multimodal AI Hackathon 2026 — Track D: Personalized Tutoring & Adaptive Learning**

An AI study companion that unifies lecture videos, textbooks (PDF), and slide decks into a **source-cited knowledge base**, then drives **adaptive assessments** and **personalized tutoring** through a **Bayesian learner model**.

---

## Demo

| Page | Feature |
|---|---|
| Upload | Drag-drop PDF/PPTX/video, YouTube URL ingest, live SSE progress |
| Tutor Chat | Source-grounded Q&A with inline citations `[1][2]`, relevance-gate refusal |
| Knowledge Map | Auto-extracted topic/prerequisite graph (React Flow) |
| Assessment | Adaptive MCQ/short/numerical quizzes; verified, deduplicated, tagged |
| Dashboard | Mastery heatmap, spaced-rep schedule, assessment history |

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- ffmpeg (for video processing)
- A Google API key (Gemini 1.5 Flash — free tier) or OpenAI API key

---

## Quick Start (without Docker)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/studycompanion
cd studycompanion
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY (required)
```

### 2. Backend

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000  
API docs: http://localhost:8000/api/docs

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:3000

---

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env — set GOOGLE_API_KEY

docker compose up --build
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000/api/docs

---

## Environment Variables

See [`.env.example`](.env.example) for all options. Required:

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Google Gemini API key (get free at ai.google.dev) |
| `WHISPER_MODEL` | `tiny`/`base`/`small`/`medium` — tradeoff speed vs. accuracy |

---

## Sample Data (for testing)

Any freely licensed lecture PDF works. Recommended:

1. **MIT OCW 6.006** Introduction to Algorithms — download any chapter PDF
2. **NPTEL** lecture slides from nptel.ac.in
3. A short YouTube lecture (paste URL in the app)

---

## Running Evaluation

After ingesting at least one source and completing a quiz:

```bash
cd backend
source venv/bin/activate   # or venv\Scripts\activate on Windows

python ../eval/run_eval.py \
  --student_id <your_student_id_from_app> \
  --api_url http://localhost:8000
```

Results are written to `eval/results/`:
- `ragas_results.json` — faithfulness, relevancy, context precision, refusal metrics
- `personalization_results.json` — adaptive vs. random baseline for 3 student profiles
- `plots/eval_results.png` — bar chart + mastery progression + comparison

> Your student ID is shown in the top-left of the app after creating a profile.

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full system design, data schemas, and API list.

```
Browser (Next.js) ←→ FastAPI ←→ ChromaDB (vector) + SQLite (relational)
                            ↕
              Gemini 1.5 Flash (LLM + VLM) + Whisper (ASR)
```

---

## Project Structure

```
studycompanion/
├── backend/          FastAPI backend + all ML services
├── frontend/         Next.js 14 frontend
├── eval/             Evaluation scripts and results
├── docs/             Architecture and design docs
├── data/             Uploaded files (gitignored)
├── chroma_db/        Vector store (gitignored)
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Key Design Decisions

| Decision | Why |
|---|---|
| Gemini 1.5 Flash | Free tier, 1M context window, native multimodal — can receive images in prompts for VLM captioning |
| ChromaDB (local) | Zero infra, persistent, supports metadata filters for per-student/per-source scoping |
| BKT over IRT | BKT is interpretable, works with few observations, well-studied in intelligent tutoring systems |
| SQLite first | Zero-config local dev; same SQLAlchemy ORM drops into PostgreSQL for production |
| Hybrid BM25+dense | Dense vectors miss exact keyword matches; BM25 misses semantic similarity; RRF fusion beats both |
| Cross-encoder reranker | Improves precision of final top-5 results significantly over embedding similarity alone |

---

## Limitations & Honest Notes

- Whisper `small` has ~5-8% WER on clear English speech; accuracy drops with accents or noisy audio.
- VLM captions may miss fine mathematical detail in dense equations — use higher-tier models for STEM.
- BKT parameters (slip/guess/transit) use defaults; ideally they'd be estimated per student from more data.
- The RAGAS-inspired eval uses a simplified faithfulness metric (citation location matching), not full NLI.
- Docker build for the frontend requires internet access for `npm install`.

---

## License

MIT
