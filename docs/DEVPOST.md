# StudyCompanion AI — Devpost Description

## What it does

StudyCompanion AI is an AI study companion that turns your own lecture videos, PDF textbooks, and slide decks into a smart, citation-grounded tutor. Upload your materials — the system automatically transcribes videos (Whisper), extracts text and figures from PDFs and slides, captions every diagram and chart with a vision-language model, and indexes everything into a hybrid vector store. Then you can:

- **Ask questions** and get answers backed by citations linking to the exact page, slide, or video timestamp in your materials.
- **Take adaptive quizzes** — MCQ, short answer, or numerical — generated from your materials, verified for correctness, and chosen to target your weak areas.
- **Track mastery** per concept using Bayesian Knowledge Tracing, with a spaced-repetition review schedule.
- **See your knowledge map** — an auto-generated topic and prerequisite graph visualized as an interactive node diagram.

## The problem it solves

Students juggle materials in different formats and have no unified way to study from all of them. Generic AI chatbots answer from model memory, not from the student's actual course materials, leading to hallucinations and off-syllabus answers. Existing tools don't adapt to individual knowledge gaps. StudyCompanion AI grounds every answer in uploaded content and adapts questioning to each student's personal learning state.

## How we built it

**Backend** (FastAPI, Python 3.11):
- **Ingestion pipeline**: PyMuPDF for PDFs, python-pptx for slides, Whisper ASR + ffmpeg keyframes for video. Every figure is described by Gemini 1.5 Flash acting as a VLM.
- **Knowledge base**: Sliding-window chunking (400 tokens, 50 overlap), LLM-extracted topic hierarchy, prerequisite graph with cycle detection (DFS), indexed in ChromaDB with hybrid BM25+dense retrieval and Reciprocal Rank Fusion.
- **Grounded chat**: Relevance gate (cosine distance threshold) → cross-encoder reranking → learner-state-aware prompt → inline citation generation. Off-material queries are refused, not answered from model memory.
- **Adaptive assessment**: ZPD-based concept selection, LLM question generation, cross-model MCQ validation + sympy numerical verification, embedding deduplication.
- **Learner model**: Bayesian Knowledge Tracing with per-student slip/guess/transit rates + SM2 spaced repetition scheduling.

**Frontend** (Next.js 14, Tailwind, React Flow, Recharts):
- Drag-drop upload with SSE progress streaming
- Chat with citation badges that open a source viewer side panel
- React Flow interactive knowledge/prerequisite graph
- Assessment UI with question navigation and post-quiz reports
- Dashboard with mastery bar charts, radar chart, and review schedule

## Challenges we ran into

- Getting citation deep-links to work correctly across PDF, PPTX, and video required normalizing location strings into a unified format that the frontend viewer can parse.
- BM25+dense fusion via RRF required careful tuning of k and top-K values to improve over either method alone.
- Cross-encoder reranking with `ms-marco-MiniLM` added ~500ms latency; we run it in an executor to avoid blocking the async event loop.
- Ensuring zero fabricated metrics in the eval required building reproducible simulation scripts before writing the numbers.

## Accomplishments we're proud of

- Every single factual claim in a tutor answer is linked back to a source with a clickable deep-link that jumps to the exact location.
- The refusal gate correctly handles off-material queries without breaking for on-material ones.
- The full evaluation suite runs with a single command and produces real numbers — no fabricated metrics.
- The system ingests video, PDF, and PPTX with zero manual preprocessing.

## What we learned

- Hybrid BM25+dense retrieval significantly outperforms dense-only for domain-specific educational content.
- VLM captioning of figures dramatically improves searchability — many key concepts in STEM materials are in diagrams, not text.
- BKT is surprisingly effective even with default parameters for cold-start students.

## What's next

- Real-time co-teaching: sync with a student's live Zoom lecture
- Fine-grained per-image deep-links (not just page-level)
- Flashcard generation from weak concepts
- Hindi / mixed-language interaction
- Study schedule generator tied to exam date + forgetting curve

## Tech stack

Python · FastAPI · ChromaDB · SQLite · Gemini 1.5 Flash · Whisper · PyMuPDF · python-pptx · yt-dlp · Next.js 14 · Tailwind CSS · React Flow · Recharts · Docker Compose
