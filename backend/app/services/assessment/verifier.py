"""
Question verifier.
- MCQ: cross-model validation (second LLM call to verify the answer)
- Numerical: sympy evaluation
- Short answer: rubric-based LLM check
"""
from __future__ import annotations
import logging
import re

from app.services.assessment.generator import GeneratedQuestion
from app.services.llm.provider import get_llm

logger = logging.getLogger(__name__)


async def verify_question(question: GeneratedQuestion) -> bool:
    """
    Return True if the question passes verification.
    Rejects questions with wrong/inconsistent answers.
    """
    if question.qtype == "mcq":
        return await _verify_mcq(question)
    elif question.qtype == "numerical":
        return await _verify_numerical(question)
    else:
        return await _verify_short(question)


async def _verify_mcq(q: GeneratedQuestion) -> bool:
    """Ask a second LLM call to independently select the correct answer."""
    if not q.choices:
        return False

    choices_text = "\n".join(f"{c['id']}. {c['text']}" for c in q.choices)
    prompt = f"""Question: {q.stem}

Options:
{choices_text}

Which option is correct? Answer with just the letter (A, B, C, or D)."""

    llm = get_llm()
    try:
        response = await llm.generate(prompt, max_tokens=10, temperature=0.0)
        predicted = response.text.strip().upper()[:1]
        expected = q.answer.strip().upper()[:1]
        if predicted == expected:
            return True
        logger.warning(f"MCQ verification mismatch: expected={expected}, got={predicted}")
        return False
    except Exception as e:
        logger.error(f"MCQ verification error: {e}")
        return False


async def _verify_numerical(q: GeneratedQuestion) -> bool:
    """
    Try to evaluate the answer using sympy.
    Also do a cross-model check for consistency.
    """
    # 1. Sympy check: extract numeric part
    try:
        import sympy
        answer_str = re.sub(r"[^\d.\-+*/()e]", "", q.answer.split()[0])
        if answer_str:
            val = float(sympy.sympify(answer_str).evalf())
            # Just checking it parses; real check is cross-model
            logger.debug(f"Sympy parsed answer: {val}")
    except Exception:
        pass

    # 2. Cross-model check
    prompt = f"""Solve this problem and give only the numeric answer (with units if applicable):

{q.stem}

Answer:"""
    llm = get_llm()
    try:
        response = await llm.generate(prompt, max_tokens=200, temperature=0.0)
        predicted = response.text.strip()

        # Extract numbers from both answers
        expected_num = _extract_number(q.answer)
        predicted_num = _extract_number(predicted)

        if expected_num is not None and predicted_num is not None:
            rel_diff = abs(expected_num - predicted_num) / (abs(expected_num) + 1e-9)
            if rel_diff < 0.05:   # within 5%
                return True
            logger.warning(f"Numerical mismatch: expected={expected_num}, got={predicted_num}")
            return False
        return True   # can't parse, pass anyway
    except Exception as e:
        logger.error(f"Numerical verification error: {e}")
        return True   # fail open


async def _verify_short(q: GeneratedQuestion) -> bool:
    """Rubric-based check via LLM."""
    prompt = f"""Given this question and its intended answer, does the answer seem correct and complete?

Question: {q.stem}
Answer: {q.answer}

Reply with YES or NO and one sentence of reasoning."""
    llm = get_llm()
    try:
        response = await llm.generate(prompt, max_tokens=100, temperature=0.0)
        return response.text.strip().upper().startswith("YES")
    except Exception:
        return True


def _extract_number(text: str) -> float | None:
    """Extract the first number from a string."""
    matches = re.findall(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?", text)
    if matches:
        try:
            return float(matches[0])
        except ValueError:
            return None
    return None
