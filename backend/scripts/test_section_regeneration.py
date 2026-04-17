"""
Validation script for section-by-section report regeneration.

Tests:
1. ReportManager.load_outline / load_section_content helpers
2. ReportManager.update_progress with regenerating_section field
3. API endpoint existence check (import only — no live network needed)
4. regenerate_section method signature on ReportAgent
5. Functional single-section regeneration rewrites section_NN.md and full_report.md
"""

import sys
import os
import json
import tempfile
import shutil
import inspect
from unittest import mock

import pytest

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.report_agent import (
    ReportAgent, ReportManager, ReportOutline, ReportSection, ReportStatus, Report
)


def _make_temp_report(tmpdir: str) -> str:
    """Create a minimal fake report folder for testing."""
    report_id = "test_regen_001"
    folder = os.path.join(tmpdir, report_id)
    os.makedirs(folder, exist_ok=True)

    outline = {
        "title": "Test Report",
        "summary": "A test summary",
        "sections": [
            {"title": "Executive Summary", "content": ""},
            {"title": "Key Findings", "content": ""},
            {"title": "Recommendations", "content": ""},
        ]
    }
    with open(os.path.join(folder, "outline.json"), "w") as f:
        json.dump(outline, f)

    for i in range(1, 4):
        with open(os.path.join(folder, f"section_{i:02d}.md"), "w") as f:
            f.write(f"## {outline['sections'][i-1]['title']}\n\nContent for section {i}.\n")

    meta = {
        "report_id": report_id,
        "simulation_id": "sim_test_001",
        "graph_id": "graph_test_001",
        "simulation_requirement": "Test scenario",
        "status": "completed",
        "outline": outline,
        "markdown_content": "",
        "created_at": "2026-04-13T00:00:00",
        "completed_at": "2026-04-13T01:00:00",
        "error": None,
        "error_details": None,
    }
    with open(os.path.join(folder, "meta.json"), "w") as f:
        json.dump(meta, f)

    progress = {
        "status": "completed",
        "progress": 100,
        "message": "Done",
        "current_section": None,
        "completed_sections": ["Executive Summary", "Key Findings", "Recommendations"],
        "updated_at": "2026-04-13T01:00:00",
    }
    with open(os.path.join(folder, "progress.json"), "w") as f:
        json.dump(progress, f)

    return report_id


@pytest.fixture()
def report_id(tmp_path):
    original_reports_dir = ReportManager.REPORTS_DIR
    ReportManager.REPORTS_DIR = str(tmp_path)
    try:
        yield _make_temp_report(str(tmp_path))
    finally:
        ReportManager.REPORTS_DIR = original_reports_dir


def test_load_outline(report_id: str):
    outline = ReportManager.load_outline(report_id)
    assert outline is not None, "load_outline returned None"
    assert outline.title == "Test Report"
    assert len(outline.sections) == 3
    assert outline.sections[1].title == "Key Findings"
    print("[PASS] ReportManager.load_outline")


def test_load_section_content(report_id: str):
    content = ReportManager.load_section_content(report_id, 2)
    assert content is not None, "load_section_content returned None for existing section"
    assert "Key Findings" in content
    missing = ReportManager.load_section_content(report_id, 99)
    assert missing is None, "load_section_content should return None for missing section"
    print("[PASS] ReportManager.load_section_content")


def test_update_progress_with_regenerating_section(report_id: str):
    ReportManager.update_progress(
        report_id, "regenerating", 30, "Regenerating section 2",
        current_section="Key Findings",
        completed_sections=["Executive Summary"],
        regenerating_section=2,
    )
    progress = ReportManager.get_progress(report_id)
    assert progress is not None
    assert progress["status"] == "regenerating"
    assert progress["regenerating_section"] == 2
    assert progress["current_section"] == "Key Findings"
    print("[PASS] ReportManager.update_progress with regenerating_section")


def test_regenerate_section_signature():
    sig = inspect.signature(ReportAgent.regenerate_section)
    params = list(sig.parameters.keys())
    assert "report_id" in params, "report_id missing from regenerate_section signature"
    assert "section_index" in params, "section_index missing from regenerate_section signature"
    assert "progress_callback" in params, "progress_callback missing from regenerate_section signature"
    print("[PASS] ReportAgent.regenerate_section signature")


def test_regenerate_section_updates_files(report_id: str):
    class DummyLLM:
        provider = "test"
        model = "dummy"

    agent = ReportAgent(
        graph_id="graph_test_001",
        simulation_id="sim_test_001",
        simulation_requirement="Test scenario",
        llm_client=DummyLLM(),
        boost_llm=DummyLLM(),
        zep_tools=object(),
    )

    def fake_generate(self, section, outline, previous_sections, progress_callback=None, section_index=0):
        assert section_index == 2
        assert section.title == "Key Findings"
        assert len(previous_sections) == 1
        assert "Executive Summary" in previous_sections[0]
        if progress_callback:
            progress_callback("regenerating", 60, "fake regeneration in progress")
        return "Regenerated content for section 2."

    with mock.patch.object(ReportAgent, "_generate_section_react", fake_generate):
        content = agent.regenerate_section(report_id, 2)

    assert content == "Regenerated content for section 2."

    section_path = ReportManager._get_section_path(report_id, 2)
    with open(section_path, "r", encoding="utf-8") as f:
        section_body = f.read()
    assert "Regenerated content for section 2." in section_body

    full_report_path = ReportManager._get_report_markdown_path(report_id)
    with open(full_report_path, "r", encoding="utf-8") as f:
        full_report = f.read()
    assert "Regenerated content for section 2." in full_report
    print("[PASS] ReportAgent.regenerate_section rewrites section and full report")


def test_api_endpoint_importable():
    from app.api.report import regenerate_section as regen_endpoint
    assert callable(regen_endpoint)
    print("[PASS] POST /api/report/<report_id>/regenerate-section endpoint importable")


def test_load_outline_returns_none_for_missing(report_id: str):
    result = ReportManager.load_outline("does_not_exist_xyz")
    assert result is None
    print("[PASS] load_outline returns None for missing report")


def main():
    # Redirect REPORTS_DIR to a temp folder so we don't touch real data
    tmpdir = tempfile.mkdtemp(prefix="mirofish_test_regen_")
    original_reports_dir = ReportManager.REPORTS_DIR
    ReportManager.REPORTS_DIR = tmpdir

    try:
        report_id = _make_temp_report(tmpdir)

        print(f"\nRunning section-regeneration validation (tmpdir={tmpdir})\n")
        test_load_outline(report_id)
        test_load_section_content(report_id)
        test_update_progress_with_regenerating_section(report_id)
        test_regenerate_section_signature()
        test_regenerate_section_updates_files(report_id)
        test_api_endpoint_importable()
        test_load_outline_returns_none_for_missing(report_id)

        print("\n[ALL TESTS PASSED]\n")
        return 0
    except AssertionError as e:
        print(f"\n[FAIL] {e}\n")
        return 1
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {e}")
        traceback.print_exc()
        return 2
    finally:
        ReportManager.REPORTS_DIR = original_reports_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
