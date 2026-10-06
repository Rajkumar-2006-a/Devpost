# DEMO SCRIPT — StudyCompanion AI
**Hackathon 2026 · Track D · 5–7 minute walkthrough**

---

## [0:00 – 0:30] Introduction

*"StudyCompanion AI solves a problem every student faces: you have lecture videos, PDF textbooks, and slide decks scattered across your computer — and no way to study from all of them at once. We built an AI tutor that ingests all your materials, builds a unified knowledge base, and provides grounded answers, adaptive quizzes, and a personalized learning path — all tied back to the exact page, slide, or timestamp in your materials."*

---

## [0:30 – 1:30] Upload & Ingestion

**Screen: Home page with upload zone**

1. *"First, we create a student profile — this initializes the learner model."* → Type name, click Get Started.
2. *"Now drag a PDF textbook into the upload zone."* → Drop a PDF.
3. *"The backend immediately starts the ingestion pipeline: PyMuPDF extracts text per page, the VLM captions any figures and diagrams, text is chunked into 400-token windows with overlap, and everything is embedded into ChromaDB."*
4. Watch progress toasts arrive via SSE.
5. *"Now let's also add a PPTX slide deck."* → Drop PPTX. 
6. *"In the background, Gemini extracts a topic hierarchy — topics, subtopics, concepts — and builds a prerequisite graph. Cycles are detected and removed."*
7. Status shows "ready" for both sources.

---

## [1:30 – 2:30] Knowledge Map

**Screen: Knowledge Map page**

*"Here's the auto-generated knowledge graph. Each node is a topic, subtopic, or concept extracted from your materials. Dashed arrows show prerequisite relationships — for instance, 'Sorting Algorithms' requires understanding 'Array Data Structures' first. This was generated entirely by the LLM, then cycle-validated. Click a node to see its description."*

→ Click a node, show the detail popup.
→ Zoom / pan the graph.

---

## [2:30 – 4:00] Grounded Tutor Chat

**Screen: Chat page**

1. *"Let's ask a question that IS in our materials."*  
   Type: *"Explain the merge sort algorithm step by step."*
   
   → Show answer with `[1][2]` citation markers.
   → *"Notice the inline citations. Each number links to the exact page or slide."*
   → Click citation badge → side panel opens with the snippet and 'Open in Viewer' link.

2. **Refusal demo** — *"Now let's ask something NOT in our materials."*  
   Type: *"What is the current price of Bitcoin?"*
   
   → Show red refusal card: *"This topic isn't covered in your uploaded materials."*  
   → *"The relevance gate fires when retrieval confidence is below our threshold. The model doesn't answer from memory — it refuses."*
   → Click "request outside knowledge" to show the clearly-labeled separate section.

3. *"The tutor also knows your weak concepts — it'll add prerequisite hints for topics where your mastery is low."*

---

## [4:00 – 5:00] Adaptive Assessment

**Screen: Assessment page**

1. *"Generate a 5-question MCQ quiz. Adaptive mode is on — this uses Bayesian Knowledge Tracing to target the zone of proximal development: concepts you're learning but not yet mastered."*
   → Click Start Quiz. Show loading.

2. *"Each question is: generated from a specific knowledge unit, cross-validated by a second LLM call, numerically verified with sympy for calculations, and checked against embedding similarity to avoid duplicates."*

3. Answer a few questions.

4. Submit → show score, per-question breakdown with explanations and source citations.

5. *"The learner model is immediately updated after each answer."*

---

## [5:00 – 5:45] Dashboard & Learner Model

**Screen: Dashboard page**

*"The dashboard shows your mastery state. Each concept has a BKT probability — how likely you are to have mastered it — plus an uncertainty estimate. The bar chart shows mastery per concept. The radar chart gives a birds-eye view. The review schedule uses SM2 spaced repetition — concepts you haven't practiced in a while bubble up."*

→ Point to the bar chart.
→ Point to review schedule.
→ *"After 3 quiz sessions, you can see mastery increasing for the concepts you answered correctly and decreasing for ones you got wrong."*

---

## [5:45 – 6:30] Evaluation Results

**Screen: `eval/results/plots/eval_results.png`** (show image)

*"We ran a reproducible evaluation suite with one command: `python eval/run_eval.py --student_id <id> --api_url http://localhost:8000`."*

- Left chart: RAG metrics — faithfulness, answer relevancy, context precision, refusal precision/recall.
- Right charts: Three simulated student profiles (Alice strong, Bob average, Carol weak) across 5 sessions each. Adaptive mode shows higher final mastery than random selection for all profiles.
- *"All numbers come from actually running the script — no fabricated metrics."*

---

## [6:30 – 7:00] Architecture & Closing

*"Under the hood: FastAPI backend with async ingestion workers, ChromaDB hybrid BM25+dense retrieval with RRF fusion, cross-encoder reranking, Gemini 1.5 Flash for LLM+VLM tasks, Whisper for video transcription, and a per-student BKT+SM2 learner model persisted in SQLite. The full system runs with `docker compose up`."*

*"StudyCompanion AI — every answer grounded in your materials, every question personalized to your learning state. Thank you!"*

---

## Key Talking Points (if asked)

- **Grounding guarantee**: The relevance gate uses cosine distance; below threshold → refusal. Cannot be bypassed.
- **Citation deep-links**: `make_citation_url()` converts `"p42"`, `"s7"`, `"1:34-2:12"` → frontend routes that jump the viewer.
- **BKT**: Four parameters per student per concept — P(L₀), P(T), P(S), P(G). Updated with every quiz answer.
- **No fabricated metrics**: Eval scripts output JSON + PNG; run them yourself.
- **Cost**: Gemini 1.5 Flash has a free tier sufficient for this demo.
