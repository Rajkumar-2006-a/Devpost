"""
Tutor chat service.
Assembles context-aware prompts with learner state and generates grounded answers.
Handles refusal when retrieval confidence is below threshold.
"""
from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass, field

from app.config import get_settings
from app.services.chat.rag import retrieve
from app.services.knowledge.vector_store import SearchResult
from app.services.llm.provider import get_llm
from app.utils.citation import make_citation_url, _location_label

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Citation:
    index: int
    unit_id: str
    source_id: str
    source_type: str
    location: str
    title: str
    snippet: str
    url: str


@dataclass
class ChatResponse:
    answer: str                            # may contain [1][2] markers
    citations: list[Citation] = field(default_factory=list)
    refused: bool = False                  # True if off-material
    outside_knowledge: str | None = None   # if user asks for it
    retrieved_units: list[str] = field(default_factory=list)   # unit_ids


async def answer(
    query: str,
    student_id: str,
    session_history: list[dict] | None = None,
    learner_state: dict | None = None,
    source_ids: list[str] | None = None,
    topic_ids: list[str] | None = None,
) -> ChatResponse:
    """
    Main tutor answer function.
    Retrieves, checks relevance gate, then generates a grounded answer.
    """
    # 1. Retrieve
    results, max_score = await retrieve(
        query=query,
        student_id=student_id,
        source_ids=source_ids,
        topic_ids=topic_ids,
    )

    # 2. Relevance gate
    if max_score < settings.relevance_threshold or not results:
        logger.info(f"Refusal triggered for query (max_score={max_score:.3f} < {settings.relevance_threshold})")
        return ChatResponse(
            answer=(
                "I couldn't find relevant information in your uploaded materials to answer this question. "
                "This topic may not be covered in the sources you've provided. "
                "\n\n*If you'd like, I can try to answer from general knowledge — just let me know.*"
            ),
            refused=True,
            citations=[],
        )

    # 3. Build context for the LLM
    context_parts = []
    citations: list[Citation] = []

    for i, result in enumerate(results, 1):
        label = _location_label(result.source_type, result.location)
        url = make_citation_url(result.source_id, result.source_type, result.location)
        context_parts.append(f"[{i}] ({label}): {result.text}")
        citations.append(Citation(
            index=i,
            unit_id=result.unit_id,
            source_id=result.source_id,
            source_type=result.source_type,
            location=result.location,
            title=label,
            snippet=result.text[:200] + "..." if len(result.text) > 200 else result.text,
            url=url,
        ))

    context = "\n\n".join(context_parts)

    # 4. Assemble tutor prompt with learner state
    learner_context = _format_learner_context(learner_state)
    history_context = _format_history(session_history)

    prompt = f"""You are a patient, expert tutor. Answer the student's question using ONLY the provided source materials. 

STUDENT CONTEXT:
{learner_context}

SOURCE MATERIALS:
{context}

CONVERSATION HISTORY:
{history_context}

STUDENT QUESTION: {query}

INSTRUCTIONS:
1. Answer concisely and clearly, using inline citations like [1], [2] to reference source materials.
2. Every factual claim must be supported by at least one citation from the SOURCE MATERIALS above.
3. If the answer requires multiple concepts, explain step by step.
4. If the student seems to be weak on a prerequisite concept (see STUDENT CONTEXT), gently note it.
5. Do NOT include information not present in the SOURCE MATERIALS. If you are unsure, say so.
6. Format your answer in markdown.

ANSWER:"""

    llm = get_llm()
    response = await llm.generate(prompt, max_tokens=2048, temperature=0.3)
    answer_text = response.text.strip()

    return ChatResponse(
        answer=answer_text,
        citations=citations,
        refused=False,
        retrieved_units=[r.unit_id for r in results],
    )


async def answer_outside_knowledge(query: str) -> str:
    """Generate an outside-knowledge answer, clearly labeled as such."""
    llm = get_llm()
    prompt = f"""You are a knowledgeable assistant. Answer the following question from general knowledge.
Be honest, accurate, and thorough.

IMPORTANT: This answer is NOT based on the student's uploaded materials.

Question: {query}

Answer:"""
    response = await llm.generate(prompt, max_tokens=1024, temperature=0.4)
    return response.text.strip()


def _format_learner_context(learner_state: dict | None) -> str:
    if not learner_state:
        return "No learner data available."
    weak = learner_state.get("weak_concepts", [])
    strong = learner_state.get("strong_concepts", [])
    return (
        f"Weak concepts (need more explanation): {', '.join(weak[:5]) or 'none'}\n"
        f"Strong concepts: {', '.join(strong[:3]) or 'none'}"
    )


def _format_history(history: list[dict] | None) -> str:
    if not history:
        return "No previous messages."
    parts = []
    for turn in history[-6:]:   # last 3 exchanges
        role = turn.get("role", "user")
        content = turn.get("content", "")[:300]
        parts.append(f"{role.upper()}: {content}")
    return "\n".join(parts)
