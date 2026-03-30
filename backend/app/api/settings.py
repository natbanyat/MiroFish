"""
Settings API - cost tier, model routing, and configuration
"""

from flask import request, jsonify
from . import settings_bp
from ..config import Config


@settings_bp.route('/cost-tier', methods=['GET'])
def get_cost_tier():
    """Return current cost tier and model routing info."""
    return jsonify({
        "success": True,
        **Config.get_tier_info()
    })


@settings_bp.route('/cost-tier', methods=['POST'])
def set_cost_tier():
    """
    Switch cost tier at runtime.

    Body: {"tier": "cheap" | "medium" | "expensive"}
    """
    data = request.get_json(silent=True) or {}
    tier = data.get("tier", "").lower().strip()

    if tier not in Config._TIER_PRESETS:
        return jsonify({
            "success": False,
            "error": f"Invalid tier '{tier}'. Must be one of: {', '.join(Config._TIER_PRESETS.keys())}"
        }), 400

    Config.COST_TIER = tier

    return jsonify({
        "success": True,
        "message": f"Cost tier switched to '{tier}'",
        **Config.get_tier_info()
    })


@settings_bp.route('/model-routing', methods=['GET'])
def get_model_routing():
    """Return per-task model routing configuration."""
    return jsonify({
        "success": True,
        **Config.get_model_routing_info()
    })


@settings_bp.route('/model-routing', methods=['POST'])
def set_model_routing():
    """
    Set model for a specific task.

    Body: {"task": "ontology", "provider": "anthropic", "model": "claude-sonnet-4-6"}
    Or to reset: {"task": "ontology", "reset": true}
    """
    data = request.get_json(silent=True) or {}
    task = data.get("task", "").strip()

    if task not in Config.TASK_TYPES:
        return jsonify({
            "success": False,
            "error": f"Unknown task '{task}'. Valid: {', '.join(Config.TASK_TYPES.keys())}"
        }), 400

    if data.get("reset"):
        Config._task_model_overrides.pop(task, None)
    else:
        provider = data.get("provider", "").strip()
        model = data.get("model", "").strip()
        if not provider or not model:
            return jsonify({"success": False, "error": "provider and model are required"}), 400
        if provider not in Config.AVAILABLE_MODELS:
            return jsonify({"success": False, "error": f"Unknown provider '{provider}'"}), 400
        Config._task_model_overrides[task] = {"provider": provider, "model": model}

    return jsonify({
        "success": True,
        **Config.get_model_routing_info()
    })


@settings_bp.route('/model-routing/reset', methods=['POST'])
def reset_model_routing():
    """Reset all per-task overrides back to defaults."""
    Config._task_model_overrides.clear()
    return jsonify({
        "success": True,
        "message": "All model routing reset to defaults",
        **Config.get_model_routing_info()
    })
