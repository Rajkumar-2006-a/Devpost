"""
Topic & concept extractor.
Given a batch of RawUnit texts, calls the LLM to:
  1. Identify a hierarchy: topics → subtopics → concepts
  2. Tag each unit with its concept/topic IDs
  3. Extract prerequisite relationships (which topic requires which)
  4. Validate the prerequisite graph for cycles (topological sort)
"""
from __future__ import annotations
import json
import logging
import uuid
from dataclasses import dataclass, field

from app.services.llm.provider import get_llm
from app.utils.cycle_detect import has_cycle, topological_sort

logger = logging.getLogger(__name__)


@dataclass
class TopicNode:
    id: str
    name: str
    description: str
    level: int            # 0=topic, 1=subtopic, 2=concept
    parent_id: str | None = None
    children: list["TopicNode"] = field(default_factory=list)


@dataclass
class TopicGraph:
    nodes: dict[str, TopicNode]           # id → node
    prerequisites: list[tuple[str, str]]  # (from_id, to_id): from_id requires to_id


async def extract_topics(texts: list[str], source_title: str) -> TopicGraph:
    """
    Extract a topic hierarchy and prerequisite graph from a list of text chunks.
    Runs the LLM on a sample/representative subset to keep cost low.
    """
    llm = get_llm()

    # Use up to 30 representative chunks (every Nth)
    sample_size = min(30, len(texts))
    step = max(1, len(texts) // sample_size)
    sample = texts[::step][:sample_size]

    combined = "\n\n---\n\n".join(sample[:20])   # ~8k token budget

    prompt = f"""You are an expert curriculum designer. Given the following excerpts from "{source_title}", extract a structured topic hierarchy.

EXCERPTS:
{combined}

Return a JSON object with this exact structure:
{{
  "topics": [
    {{
      "id": "t1",
      "name": "Topic Name",
      "description": "Brief description",
      "level": 0,
      "parent_id": null,
      "subtopics": [
        {{
          "id": "t1_1",
          "name": "Subtopic Name",
          "description": "Brief description",
          "level": 1,
          "parent_id": "t1",
          "concepts": [
            {{
              "id": "t1_1_c1",
              "name": "Concept Name",
              "description": "Brief description",
              "level": 2,
              "parent_id": "t1_1"
            }}
          ]
        }}
      ]
    }}
  ],
  "prerequisites": [
    {{"from": "t1_1", "to": "t2", "reason": "Why t1_1 requires t2"}}
  ]
}}

Rules:
- Use 3-8 top-level topics. Each should have 2-5 subtopics. Each subtopic should have 2-6 concepts.
- Prerequisites: from_id REQUIRES to_id (i.e., you must know to_id before from_id).
- Do NOT create circular prerequisites.
- IDs must be unique short strings.
- Return ONLY valid JSON, no explanation."""

    try:
        response = await llm.generate(prompt, max_tokens=4096, temperature=0.1)
        text = response.text.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Topic extraction failed: {e}")
        # Return a minimal fallback
        return _fallback_graph(source_title)

    # Flatten into TopicGraph
    nodes: dict[str, TopicNode] = {}
    prerequisites: list[tuple[str, str]] = []

    def _flatten(items, parent_id=None):
        for item in items:
            node = TopicNode(
                id=item["id"],
                name=item["name"],
                description=item.get("description", ""),
                level=item.get("level", 0),
                parent_id=parent_id,
            )
            nodes[node.id] = node
            # Recurse into subtopics / concepts
            for key in ("subtopics", "concepts"):
                if key in item:
                    _flatten(item[key], parent_id=item["id"])

    _flatten(data.get("topics", []))

    for prereq in data.get("prerequisites", []):
        prerequisites.append((prereq["from"], prereq["to"]))

    # Validate: remove edges that create cycles
    edges = list(prerequisites)
    adj = {n: [] for n in nodes}
    valid_prereqs: list[tuple[str, str]] = []
    for f, t in edges:
        if f in adj and t in adj:
            adj[f].append(t)
            if not has_cycle(adj):
                valid_prereqs.append((f, t))
            else:
                # Remove this edge
                adj[f].pop()
                logger.warning(f"Removed cyclic prerequisite: {f} → {t}")

    return TopicGraph(nodes=nodes, prerequisites=valid_prereqs)


async def tag_units(units_texts: list[str], topic_graph: TopicGraph) -> list[tuple[list[str], list[str]]]:
    """
    For each unit, return (topic_ids, concept_ids) by asking the LLM to tag it.
    Runs in batches of 10 to manage token usage.
    """
    llm = get_llm()
    topic_index = {n.name: n.id for n in topic_graph.nodes.values()}
    concept_nodes = {n.id: n.name for n in topic_graph.nodes.values() if n.level == 2}

    # Build a compact listing
    topic_list = "\n".join(
        f"- [{n.id}] {n.name} (level={n.level})"
        for n in topic_graph.nodes.values()
    )

    results: list[tuple[list[str], list[str]]] = []
    batch_size = 10

    for i in range(0, len(units_texts), batch_size):
        batch = units_texts[i:i+batch_size]
        prompt = f"""Given these topics/concepts:
{topic_list}

Tag each of the following text chunks with the most relevant topic IDs and concept IDs.

{chr(10).join(f'CHUNK {j}: {t[:300]}' for j, t in enumerate(batch))}

Return a JSON array with one object per chunk:
[{{"chunk": 0, "topic_ids": ["t1"], "concept_ids": ["t1_1_c1"]}}, ...]

Return ONLY valid JSON."""

        try:
            response = await llm.generate(prompt, max_tokens=1024, temperature=0.0)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            tags = json.loads(text)
            for item in sorted(tags, key=lambda x: x["chunk"]):
                results.append((item.get("topic_ids", []), item.get("concept_ids", [])))
        except Exception as e:
            logger.error(f"Unit tagging batch failed: {e}")
            results.extend([([], []) for _ in batch])

    return results


def _fallback_graph(source_title: str) -> TopicGraph:
    """Minimal fallback if LLM extraction fails."""
    node = TopicNode(id="t1", name=source_title, description="Main topic", level=0)
    return TopicGraph(nodes={"t1": node}, prerequisites=[])
