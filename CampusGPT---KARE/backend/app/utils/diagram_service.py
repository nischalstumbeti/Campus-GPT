"""Diagram generation for workflow/architecture queries. Adapted from reference CampusGPT."""
import json
import asyncio

from app.config import get_settings

settings = get_settings()


def _get_genai():
    if not settings.GEMINI_API_KEY:
        return None
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai


async def decide_diagram(query: str) -> dict:
    """Decide if a diagram is needed based on query type (from reference)."""
    genai = _get_genai()
    if not genai:
        return {"needs_diagram": False, "diagram_query": ""}

    prompt = f"""
You decide whether a diagram would help answer this question.
Rules: workflow, process, phases, architecture, steps → diagram needed
Factual, list, definition → no diagram

Return ONLY JSON:
{{"needs_diagram": true/false, "diagram_query": "instruction if needed else empty string"}}

Examples:
- "What are phases of admission?" → {{"needs_diagram": true, "diagram_query": "Flowchart of admission process phases"}}
- "What is the hostel fee?" → {{"needs_diagram": false, "diagram_query": ""}}

User Query: "{query}"
"""
    try:
        model = genai.GenerativeModel(settings.GEMINI_CHAT_MODEL)
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = (response.text or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    except Exception:
        pass
    return {"needs_diagram": False, "diagram_query": ""}


async def generate_diagram(diagram_query: str, chunks: list[str]) -> dict | None:
    """Generate Mermaid diagram from context (from reference)."""
    genai = _get_genai()
    if not genai or not diagram_query or not chunks:
        return None

    context = "\n\n".join(f"[CHUNK {i+1}]\n{c}" for i, c in enumerate(chunks[:5]))

    prompt = f"""
You are a diagram generator. Return ONLY valid JSON.

Output format:
{{"explanation": "2-4 line explanation", "diagram": "Mermaid code with \\n between lines"}}

Rules: Use ONLY context. No external knowledge. Valid Mermaid: flowchart, graph, sequenceDiagram.
Escape newlines in diagram as \\n. No markdown, no ``` blocks.

CONTEXT:
{context}

USER QUESTION: {diagram_query}

JSON only:
"""
    try:
        model = genai.GenerativeModel(settings.GEMINI_CHAT_MODEL)
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = (response.text or "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(text[start : end + 1])
            diagram = (data.get("diagram") or "").replace("\\n", "\n").strip()
            valid_starts = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram")
            if diagram and any(diagram.startswith(s) for s in valid_starts):
                return {
                    "success": True,
                    "explanation": data.get("explanation", ""),
                    "diagram": diagram,
                }
    except Exception:
        pass
    return None
