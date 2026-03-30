"""
Scenarios API — library of saved simulation prompts + AI-assisted generation
"""

import os
import json
import uuid
from datetime import datetime
from flask import request, jsonify
from . import scenarios_bp
from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.scenarios')

SCENARIOS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'scenarios')

SEED_SYSTEM_PROMPT = """\
You generate reality seed documents for a multi-agent social simulation engine.
A reality seed is raw background material (news, reports, timelines, stakeholder profiles) that gets ingested into a knowledge graph.

Rules:
- Every paragraph must contain at least 2 named entities and 1 explicit relationship
- Use real/realistic names, titles, organizations — never placeholders
- Include: executive summary, key stakeholders (8-15), timeline, regulatory context, public discourse, data points, unresolved questions
- Write 3000-5000 words of dense, factual prose
- Language must match the user's input language
- Write as a real briefing document, not fiction
- Most important content first (system truncates from bottom)

Output format: pure Markdown, starting with # Title"""


GENERATOR_SYSTEM_PROMPT = """\
You are a prompt engineer for MiroFish, a multi-agent social simulation engine.
Given a user's natural-language scenario description, produce a structured simulation prompt.

Return JSON with these exact keys:
{
  "title": "Short title (under 60 chars)",
  "scenario": "1-2 sentences. Specific event, named actors, domain.",
  "prediction_question": "Single question: What happens if/when...",
  "key_actors": [
    {"name": "Actor name or role", "stake": "Their position and likely behavior"}
  ],
  "time_scope": {
    "trigger": "What starts the clock",
    "window": "24h / 72h / 7d / 30d",
    "phases": "e.g. initial shock -> media amplification -> institutional response"
  },
  "constraints": ["Hard fact 1", "Hard fact 2"],
  "success_metrics": ["Measurable metric 1", "Measurable metric 2"],
  "background_notes": "Key context the user should attach as documents",
  "estimated_actors": 10,
  "recommended_window_hours": 72
}

Rules:
- Be specific, not generic. Name real entities.
- 5-15 actors spanning supporters, opponents, neutral, institutions, media.
- One prediction question only.
- Default to 72h window unless scenario clearly needs longer.
- Output language must match the user's input language."""


def _ensure_dir():
    os.makedirs(SCENARIOS_DIR, exist_ok=True)


def _scenario_path(scenario_id):
    return os.path.join(SCENARIOS_DIR, f'{scenario_id}.json')


def _scenario_to_prompt(data):
    """Convert structured scenario JSON to the flat prompt text MiroFish consumes."""
    parts = [f"## Scenario\n\n{data.get('scenario', '')}"]

    pq = data.get('prediction_question', '')
    if pq:
        parts.append(f"## Prediction Question\n\n{pq}")

    actors = data.get('key_actors', [])
    if actors:
        lines = [f"- {a['name']} -- {a['stake']}" for a in actors]
        parts.append("## Key Actors\n\n" + "\n".join(lines))

    ts = data.get('time_scope', {})
    if ts:
        lines = []
        if ts.get('trigger'):
            lines.append(f"- Trigger event: {ts['trigger']}")
        if ts.get('window'):
            lines.append(f"- Prediction window: {ts['window']}")
        if ts.get('phases'):
            lines.append(f"- Expected phases: {ts['phases']}")
        if lines:
            parts.append("## Time Scope\n\n" + "\n".join(lines))

    constraints = data.get('constraints', [])
    if constraints:
        parts.append("## Constraints & Assumptions\n\n" + "\n".join(f"- {c}" for c in constraints))

    metrics = data.get('success_metrics', [])
    if metrics:
        parts.append("## Success Metrics\n\n" + "\n".join(f"- {m}" for m in metrics))

    bg = data.get('background_notes', '')
    if bg:
        parts.append(f"## Background Material\n\n{bg}")

    return "\n\n".join(parts)


@scenarios_bp.route('', methods=['GET'])
def list_scenarios():
    """List all saved scenarios."""
    _ensure_dir()
    scenarios = []
    for fname in sorted(os.listdir(SCENARIOS_DIR), reverse=True):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(SCENARIOS_DIR, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
            scenarios.append({
                "id": data.get("id"),
                "title": data.get("title", "Untitled"),
                "scenario": data.get("scenario", ""),
                "created_at": data.get("created_at", ""),
                "estimated_actors": data.get("estimated_actors", 0),
                "recommended_window_hours": data.get("recommended_window_hours", 72),
            })
        except Exception:
            continue
    return jsonify({"success": True, "scenarios": scenarios})


@scenarios_bp.route('/<scenario_id>', methods=['GET'])
def get_scenario(scenario_id):
    """Get a single scenario with full data + rendered prompt."""
    path = _scenario_path(scenario_id)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Scenario not found"}), 404
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["rendered_prompt"] = _scenario_to_prompt(data)
    return jsonify({"success": True, **data})


@scenarios_bp.route('', methods=['POST'])
def save_scenario():
    """Save a scenario (from AI generation or manual creation)."""
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("scenario"):
        return jsonify({"success": False, "error": "title and scenario are required"}), 400

    scenario_id = data.get("id") or f"sc_{uuid.uuid4().hex[:12]}"
    data["id"] = scenario_id
    data.setdefault("created_at", datetime.now().isoformat())

    _ensure_dir()
    with open(_scenario_path(scenario_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    data["rendered_prompt"] = _scenario_to_prompt(data)
    return jsonify({"success": True, **data})


@scenarios_bp.route('/<scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    """Delete a saved scenario."""
    path = _scenario_path(scenario_id)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"success": True})


@scenarios_bp.route('/generate', methods=['POST'])
def generate_scenario():
    """
    AI-assisted scenario generation.

    Body: {"description": "natural language scenario description"}
    Returns: structured scenario JSON + rendered prompt text
    """
    data = request.get_json(silent=True) or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"success": False, "error": "description is required"}), 400

    try:
        # Use boost model for quality generation
        llm = LLMClient.from_boost_config() or LLMClient()
        raw = llm.chat(
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
                {"role": "user", "content": description}
            ],
            temperature=0.4,
            max_tokens=2048
        )

        # Extract JSON from response (may be wrapped in markdown code block)
        import re
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', raw.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned).strip()
        result = json.loads(cleaned)

        # Add metadata
        result["id"] = f"sc_{uuid.uuid4().hex[:12]}"
        result["created_at"] = datetime.now().isoformat()
        result["source"] = "ai_generated"
        result["original_description"] = description
        result["rendered_prompt"] = _scenario_to_prompt(result)

        return jsonify({"success": True, **result})

    except Exception as e:
        logger.error(f"Scenario generation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


SEEDS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'seeds')


@scenarios_bp.route('/generate-seed', methods=['POST'])
def generate_seed():
    """
    AI-generate a reality seed document from a scenario description.

    Body: {"description": "scenario description"}
    Returns: {"filename": "...", "path": "...", "content": "...", "word_count": N}
    """
    data = request.get_json(silent=True) or {}
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"success": False, "error": "description is required"}), 400

    try:
        llm = LLMClient.from_boost_config() or LLMClient()
        # Reasoning models (gpt-5+) burn tokens on thinking — need higher limit
        # for long-form document generation
        token_limit = 16384 if llm._uses_max_completion_tokens() else 4096
        content = llm.chat(
            messages=[
                {"role": "system", "content": SEED_SYSTEM_PROMPT},
                {"role": "user", "content": description}
            ],
            temperature=0.5,
            max_tokens=token_limit
        )

        if not content or len(content.strip()) < 100:
            return jsonify({"success": False, "error": "Generated content too short"}), 500

        # Extract title from first markdown heading
        import re
        title_match = re.match(r'^#\s+(.+)', content.strip())
        title = title_match.group(1).strip() if title_match else "Reality Seed"

        # Create slug filename
        slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', title).strip('-').lower()[:60]
        filename = f"{slug}.md"

        # Save to uploads/seeds/
        os.makedirs(SEEDS_DIR, exist_ok=True)
        filepath = os.path.join(SEEDS_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        word_count = len(content.split())
        logger.info(f"Reality seed generated: {filename} ({word_count} words)")

        return jsonify({
            "success": True,
            "filename": filename,
            "path": filepath,
            "title": title,
            "word_count": word_count,
            "content_preview": content[:500],
        })

    except Exception as e:
        logger.error(f"Seed generation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
