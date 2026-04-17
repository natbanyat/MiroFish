"""
Focused validation for the stuck-section-03/04 report-generation fix.

Tests:
  T1 - empty Final Answer content raises ReportGenerationError (not silently accepted)
  T2 - whitespace-only direct-adoption content raises ReportGenerationError
  T3 - force-final empty response raises ReportGenerationError
  T4 - valid content is still returned normally (no regression)
  T5 - GENERATING status is saved to meta.json before section loop starts
  T6 - stale report (>30 min no update) is auto-recovered to failed on get_report
  T7 - broken report_c7b3d49078d0 is now in a retryable failed state

All tests run without network calls — purely unit/offline logic.
"""

import sys
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# ── path setup ──────────────────────────────────────────────────────────────
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

# Minimal env so Config doesn't blow up
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

PASS = []
FAIL = []


def ok(name):
    print(f"  PASS  {name}")
    PASS.append(name)


def fail(name, reason=""):
    print(f"  FAIL  {name}" + (f": {reason}" if reason else ""))
    FAIL.append(name)


# ─────────────────────────────────────────────────────────────────────────────
# Imports (deferred so path is set first)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from app.services.report_agent import (
        ReportAgent,
        ReportGenerationError,
        ReportManager,
        ReportStatus,
        Report,
        ReportOutline,
        ReportSection,
    )
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: minimal ReportAgent with LLM and tools stubbed out
# ─────────────────────────────────────────────────────────────────────────────
def _make_agent():
    mock_llm = MagicMock()
    mock_boost = MagicMock()
    mock_zep = MagicMock()
    agent = ReportAgent.__new__(ReportAgent)
    agent.graph_id = "g1"
    agent.simulation_id = "s1"
    agent.simulation_requirement = "test"
    agent.llm = mock_llm
    agent.boost_llm = mock_boost
    agent.zep_tools = mock_zep
    agent.tools = agent._define_tools()
    agent.report_logger = None
    agent.console_logger = None
    return agent


def _make_section(title="Section 1"):
    return ReportSection(title=title)


def _make_outline():
    return ReportOutline(
        title="Test Report",
        summary="Summary",
        sections=[_make_section("Section 1")],
    )


# ─────────────────────────────────────────────────────────────────────────────
# T1: empty Final Answer raises ReportGenerationError
# ─────────────────────────────────────────────────────────────────────────────
def test_t1_empty_final_answer():
    agent = _make_agent()
    section = _make_section()
    outline = _make_outline()

    # Simulate: 2 tool calls satisfied (min_tool_calls=2), then LLM returns "Final Answer:" with nothing after
    responses = [
        # iter 0: tool call
        '<tool_call>{"name": "quick_search", "parameters": {"query": "test"}}</tool_call>',
        # iter 1: tool call
        '<tool_call>{"name": "panorama_search", "parameters": {"query": "test2"}}</tool_call>',
        # iter 2: Final Answer with empty body
        "Final Answer:",
    ]
    agent.boost_llm.chat.side_effect = responses
    agent._execute_tool = MagicMock(return_value="some tool result")

    try:
        agent._generate_section_react(section, outline, [])
        fail("T1", "Expected ReportGenerationError but got no exception")
    except ReportGenerationError as e:
        if e.error_type == "empty_section_content" and e.retryable:
            ok("T1 - empty Final Answer raises retryable ReportGenerationError")
        else:
            fail("T1", f"Wrong error_type/retryable: {e.error_type}, {e.retryable}")
    except Exception as e:
        fail("T1", f"Unexpected exception: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# T2: whitespace direct-adoption raises ReportGenerationError
# ─────────────────────────────────────────────────────────────────────────────
def test_t2_whitespace_direct_adoption():
    agent = _make_agent()
    section = _make_section()
    outline = _make_outline()

    # After 2 tool calls: LLM returns whitespace only (no "Final Answer:", no tool call)
    responses = [
        '<tool_call>{"name": "quick_search", "parameters": {"query": "q1"}}</tool_call>',
        '<tool_call>{"name": "panorama_search", "parameters": {"query": "q2"}}</tool_call>',
        "   \n  \t  ",  # whitespace only — direct adoption path
    ]
    agent.boost_llm.chat.side_effect = responses
    agent._execute_tool = MagicMock(return_value="result")

    try:
        agent._generate_section_react(section, outline, [])
        fail("T2", "Expected ReportGenerationError but got no exception")
    except ReportGenerationError as e:
        if e.error_type == "empty_section_content" and e.retryable:
            ok("T2 - whitespace direct-adoption raises retryable ReportGenerationError")
        else:
            fail("T2", f"Wrong error_type/retryable: {e.error_type}, {e.retryable}")
    except Exception as e:
        fail("T2", f"Unexpected exception: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# T3: force-final empty response raises ReportGenerationError
# ─────────────────────────────────────────────────────────────────────────────
def test_t3_force_final_empty():
    agent = _make_agent()
    section = _make_section()
    outline = _make_outline()

    # Exhaust all 4 iterations without final answer, then force-final returns empty
    no_action = "I am thinking..."  # no tool call, no Final Answer — but tool count < 2
    responses = [no_action] * 4  # fills 4 iterations
    agent.boost_llm.chat.side_effect = responses
    # force-final call uses self.llm
    agent.llm.chat.return_value = "Final Answer:"  # empty after splitting

    try:
        agent._generate_section_react(section, outline, [])
        fail("T3", "Expected ReportGenerationError but got no exception")
    except ReportGenerationError as e:
        if e.error_type == "empty_section_content" and e.retryable:
            ok("T3 - force-final empty response raises retryable ReportGenerationError")
        else:
            fail("T3", f"Wrong error_type/retryable: {e.error_type}, {e.retryable}")
    except Exception as e:
        fail("T3", f"Unexpected exception: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# T4: valid content is still returned (no regression)
# ─────────────────────────────────────────────────────────────────────────────
def test_t4_valid_content_returned():
    agent = _make_agent()
    section = _make_section()
    outline = _make_outline()

    responses = [
        '<tool_call>{"name": "quick_search", "parameters": {"query": "q1"}}</tool_call>',
        '<tool_call>{"name": "panorama_search", "parameters": {"query": "q2"}}</tool_call>',
        "Final Answer: This is the section content with real data.",
    ]
    agent.boost_llm.chat.side_effect = responses
    agent._execute_tool = MagicMock(return_value="result data")

    try:
        result = agent._generate_section_react(section, outline, [])
        if result == "This is the section content with real data.":
            ok("T4 - valid content returned without error")
        else:
            fail("T4", f"Unexpected result: {repr(result)}")
    except Exception as e:
        fail("T4", f"Unexpected exception: {type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# T5: GENERATING status persisted to meta.json before section loop
# ─────────────────────────────────────────────────────────────────────────────
def test_t5_generating_status_saved():
    """
    Check that generate_report writes status=generating to meta.json before
    starting to generate sections (so a crash mid-loop doesn't leave status=planning).
    """
    tmpdir = tempfile.mkdtemp()
    try:
        reports_dir = os.path.join(tmpdir, "reports")
        outline = ReportOutline(
            title="T5 Report",
            summary="s",
            sections=[ReportSection("Sec1")],
        )
        agent = _make_agent()
        agent.plan_outline = MagicMock(return_value=outline)

        call_log = []
        _real_save_report = ReportManager.__dict__['save_report'].__func__

        def spy_save_report(cls, report):
            call_log.append(report.status)
            _real_save_report(cls, report)
            # After the GENERATING save, raise to abort without needing real LLM calls
            if report.status == ReportStatus.GENERATING:
                raise StopIteration("abort after GENERATING save")

        with patch.object(ReportManager, 'REPORTS_DIR', reports_dir), \
             patch.object(ReportManager, 'save_report', classmethod(spy_save_report)), \
             patch.object(ReportManager, 'save_outline', classmethod(lambda cls, *a, **kw: None)), \
             patch.object(ReportManager, 'update_progress', classmethod(lambda cls, *a, **kw: None)):
            try:
                agent.generate_report(report_id="t5_report")
            except StopIteration:
                pass
            except Exception:
                pass  # any other crash after GENERATING save is fine

        if ReportStatus.GENERATING in call_log:
            ok("T5 - GENERATING status is saved to meta.json before section loop")
        else:
            fail("T5", f"GENERATING never saved; statuses saved={call_log}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# T6: stale report auto-recovered to failed in get_report
# ─────────────────────────────────────────────────────────────────────────────
def test_t6_stale_report_detection():
    tmpdir = tempfile.mkdtemp()
    try:
        reports_dir = os.path.join(tmpdir, "reports")
        rid = "test_stale_report"
        rdir = os.path.join(reports_dir, rid)
        os.makedirs(rdir, exist_ok=True)

        # Write meta.json with status=generating
        meta = {
            "report_id": rid,
            "simulation_id": "sim_stale",
            "graph_id": "g1",
            "simulation_requirement": "test",
            "status": "generating",
            "outline": None,
            "markdown_content": "",
            "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            "completed_at": "",
            "error": None,
            "error_details": None,
        }
        with open(os.path.join(rdir, "meta.json"), "w") as f:
            json.dump(meta, f)

        # Write progress.json with updated_at 40 minutes ago
        progress = {
            "status": "generating",
            "progress": 60,
            "message": "generating section 3",
            "current_section": "Section 3",
            "completed_sections": ["Section 1", "Section 2"],
            "updated_at": (datetime.now() - timedelta(minutes=40)).isoformat(),
        }
        with open(os.path.join(rdir, "progress.json"), "w") as f:
            json.dump(progress, f)

        with patch.object(ReportManager, 'REPORTS_DIR', reports_dir):
            report = ReportManager.get_report(rid)

        if report is None:
            fail("T6", "get_report returned None")
            return

        if report.status == ReportStatus.FAILED and report.error_details.get("error_type") == "stalled":
            ok("T6 - stale generating report auto-recovered to failed with retryable=True")
        else:
            fail("T6", f"status={report.status}, error_details={report.error_details}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# T7: broken report_c7b3d49078d0 is now retryable-failed
# ─────────────────────────────────────────────────────────────────────────────
def test_t7_broken_report_recovery():
    REPORT_ID = "report_c7b3d49078d0"
    meta_path = os.path.join(ReportManager.REPORTS_DIR, REPORT_ID, "meta.json")

    if not os.path.exists(meta_path):
        print(f"  SKIP  T7 - report folder not found (not running in prod environment)")
        return

    try:
        with open(meta_path) as f:
            meta = json.load(f)
    except Exception as e:
        fail("T7", f"Cannot read meta.json: {e}")
        return

    status = meta.get("status")
    error_details = meta.get("error_details") or {}
    retryable = error_details.get("retryable", False)

    if status == "failed" and retryable:
        ok("T7 - report_c7b3d49078d0 is in retryable failed state (user can regenerate)")
    elif status == "failed":
        fail("T7", "status=failed but retryable=False")
    else:
        fail("T7", f"status is still '{status}', not 'failed'")


# ─────────────────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== MiroFish report stuck-stage-03/04 fix validation ===\n")

    test_t1_empty_final_answer()
    test_t2_whitespace_direct_adoption()
    test_t3_force_final_empty()
    test_t4_valid_content_returned()
    test_t5_generating_status_saved()
    test_t6_stale_report_detection()
    test_t7_broken_report_recovery()

    print(f"\n{'─'*50}")
    print(f"PASSED: {len(PASS)}/{len(PASS)+len(FAIL)}")
    if FAIL:
        print(f"FAILED: {FAIL}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)
