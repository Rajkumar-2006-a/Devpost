"""
Citation deep-link formatter.
Converts a (source_id, source_type, location) triple into a URL
that the frontend viewer can parse to jump to the exact page/slide/timestamp.
"""
from __future__ import annotations


def make_citation_url(source_id: str, source_type: str, location: str) -> str:
    """
    Build a frontend-navigable deep link.

    Examples:
      pdf, "p42"    → /viewer/pdf/{source_id}?page=42
      pptx, "s7"    → /viewer/slide/{source_id}?slide=7
      video, "1:34-2:12" → /viewer/video/{source_id}?t=94
      video, "1:34" → /viewer/video/{source_id}?t=94
    """
    if source_type == "pdf":
        page_num = _parse_page(location)
        return f"/viewer/pdf/{source_id}?page={page_num}"
    elif source_type == "pptx":
        slide_num = _parse_slide(location)
        return f"/viewer/slide/{source_id}?slide={slide_num}"
    elif source_type == "video":
        start_sec = _parse_video_start(location)
        return f"/viewer/video/{source_id}?t={start_sec}"
    return f"/viewer/{source_type}/{source_id}"


def _parse_page(location: str) -> int:
    """Parse "p42" → 42."""
    try:
        return int(location.lstrip("p"))
    except ValueError:
        return 1


def _parse_slide(location: str) -> int:
    """Parse "s7" → 7."""
    try:
        return int(location.lstrip("s"))
    except ValueError:
        return 1


def _parse_video_start(location: str) -> int:
    """
    Parse "1:34-2:12" → 94 (start in seconds).
    Parse "1:34" → 94.
    """
    part = location.split("-")[0].strip()
    try:
        parts = part.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return int(part)
    except ValueError:
        return 0


def format_inline_citations(citations: list[dict]) -> str:
    """
    Format a list of citations as inline markers [1][2] and return
    a citation block string for the answer.
    """
    lines = []
    for i, c in enumerate(citations, 1):
        url = make_citation_url(c["source_id"], c["source_type"], c["location"])
        label = _location_label(c["source_type"], c["location"])
        lines.append(f"[{i}] {c.get('title', c['source_id'])} — {label} ({url})")
    return "\n".join(lines)


def _location_label(source_type: str, location: str) -> str:
    if source_type == "pdf":
        return f"Page {_parse_page(location)}"
    elif source_type == "pptx":
        return f"Slide {_parse_slide(location)}"
    elif source_type == "video":
        return f"Timestamp {location}"
    return location
