# Grounding Method

## The Problem

LLMs hallucinate. For an educational tool, an incorrect answer presented as fact is worse than no answer. StudyCompanion AI is designed so that **every factual claim must be traceable to an uploaded source location**.

## The RAG Pipeline

### 1. Retrieval
For every user query:
- **Dense retrieval**: Embed the query with `text-embedding-004`, query ChromaDB HNSW index (top-20 results, cosine similarity).
- **Sparse retrieval**: BM25 on the same candidate corpus (exact keyword matching).
- **Fusion**: Reciprocal Rank Fusion (`1/(k+rank)`, k=60) merges both rankings into top-10.

### 2. Reranking
The top-10 fused results are passed to a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) that scores each (query, passage) pair. Reranked top-5 go to the LLM.

### 3. Relevance Gate
The maximum cross-encoder score is checked against `RELEVANCE_THRESHOLD` (default 0.35).
- **Below threshold**: Response is "not covered in your material." No answer is fabricated.
- **Above threshold**: Proceed to generation.

### 4. Grounded Generation
The prompt explicitly lists numbered context passages and instructs:
> "Every factual claim must be supported by at least one citation from the SOURCE MATERIALS above. Do NOT include information not present in the SOURCE MATERIALS."

The LLM produces inline citation markers `[1]`, `[2]`, etc.

### 5. Citation Deep-Links
Each citation is mapped to a deep-link URL:
```
PDF page 42   → /viewer/pdf/{source_id}?page=42
Slide 7       → /viewer/slide/{source_id}?slide=7
Video 1:34    → /viewer/video/{source_id}?t=94
```
Clicking a citation opens the exact location in the embedded viewer.

## Off-Material Query Handling

Off-material queries (e.g., current events, topics not in uploaded materials) trigger:
1. **Primary response**: Refusal message with explanation.
2. **Optional outside-knowledge response**: Only if the user explicitly requests it, clearly labeled "⚠️ Outside Your Materials" in a visually distinct amber-bordered section.

This separation ensures students never confuse model-generated text for source-backed content.

## Limitations

- Relevance threshold is a single global hyperparameter; domain-specific tuning may improve refusal accuracy.
- If the uploaded material itself contains errors, the tutor will faithfully reproduce them.
- Very long queries may dilute retrieval quality; question decomposition would help.
