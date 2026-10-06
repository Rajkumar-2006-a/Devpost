"""
Question generator.
Generates MCQ, short answer, and numerical questions grounded in knowledge units.
Every question is tagged with topic, concept, source location, and difficulty.
"""
from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass

from app.services.knowledge.vector_store import SearchResult
from app.services.llm.provider import get_llm

logger = logging.getLogger(__name__)


@dataclass
class GeneratedQuestion:
    stem: str
    qtype: str                        # mcq | short | numerical
    choices: list[dict] | None        # [{id, text, correct}] for MCQ
    answer: str
    explanation: str
    difficulty: int                   # 1-5
    topic_id: str | None
    concept_id: str | None
    source_unit_id: str
    source_location: str


async def generate_question(
    unit: SearchResult,
    qtype: str = "mcq",
    difficulty: int = 3,
    topic_id: str | None = None,
    concept_id: str | None = None,
) -> GeneratedQuestion | None:
    """
    Generate a single question grounded in the given knowledge unit.
    Returns None if generation fails after retries.
    """
    llm = get_llm()

    qtype_instructions = {
        "mcq": (
            "Generate a multiple-choice question with exactly 4 options (A, B, C, D). "
            "One option must be clearly correct; the others must be plausible distractors. "
            "Return JSON: {\"stem\": \"...\", \"choices\": [{\"id\": \"A\", \"text\": \"...\", \"correct\": false}, ...], "
            "\"answer\": \"A\", \"explanation\": \"...\", \"difficulty\": 3}"
        ),
        "short": (
            "Generate a short-answer question (1-3 sentence answer expected). "
            "Return JSON: {\"stem\": \"...\", \"answer\": \"...\", \"explanation\": \"...\", \"difficulty\": 3}"
        ),
        "numerical": (
            "Generate a numerical question that requires calculation. Include units where relevant. "
            "Return JSON: {\"stem\": \"...\", \"answer\": \"<numeric value with units>\", "
            "\"explanation\": \"<step-by-step solution>\", \"difficulty\": 3}"
        ),
    }

    prompt = f"""You are an expert exam question writer. Create one {qtype} question based ONLY on the following source material.

SOURCE MATERIAL (from {unit.source_type}, location: {unit.location}):
{unit.text}

TARGET DIFFICULTY: {difficulty}/5 (1=very easy, 5=very hard)

{qtype_instructions[qtype]}

RULES:
- The question MUST be answerable from the source material above.
- Do NOT ask about information not present in the source.
- Set difficulty to {difficulty}.
- Return ONLY valid JSON, no explanation outside the JSON."""

    try:
        response = await llm.generate(prompt, max_tokens=1024, temperature=0.7)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)

        choices = None
        if qtype == "mcq":
            choices = data.get("choices", [])

        return GeneratedQuestion(
            stem=data["stem"],
            qtype=qtype,
            choices=choices,
            answer=str(data.get("answer", "")),
            explanation=data.get("explanation", ""),
            difficulty=int(data.get("difficulty", difficulty)),
            topic_id=topic_id,
            concept_id=concept_id,
            source_unit_id=unit.unit_id,
            source_location=unit.location,
        )
    except Exception as e:
        logger.error(f"Question generation failed for unit {unit.unit_id}: {e}")
        return None
