"""
Focused offline validation for late-stage empty/ellipsis section-content recovery.

Tests:
  T1 - whitespace/ellipsis direct-adoption now recovers to real content
  T2 - empty Final Answer now gets one recovery attempt
  T3 - placeholder recovery still fails with retryable empty_section_content
  T4 - valid content path still works and does not trigger recovery
  T5 - force-final placeholder output can recover on the single fallback attempt
"""

import os
import sys
from unittest.mock import MagicMock


BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

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


try:
    from app.services.report_agent import (
        ReportAgent,
        ReportGenerationError,
        ReportOutline,
        ReportSection,
    )
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)


def _make_agent():
    agent = ReportAgent.__new__(ReportAgent)
    agent.graph_id = "g1"
    agent.simulation_id = "s1"
    agent.simulation_requirement = "test"
    agent.llm = MagicMock()
    agent.boost_llm = MagicMock()
    agent.zep_tools = MagicMock()
    agent.tools = agent._define_tools()
    agent.report_logger = None
    agent.console_logger = None
    return agent


def _make_outline():
    return ReportOutline(
        title="Test Report",
        summary="Summary",
        sections=[ReportSection(title="Section 1")],
    )


def _tool_call(name, query):
    return f'<tool_call>{{"name": "{name}", "parameters": {{"query": "{query}"}}}}</tool_call>'


def test_t1_direct_adoption_recovery():
    agent = _make_agent()
    agent.boost_llm.chat.side_effect = [
        _tool_call("quick_search", "q1"),
        _tool_call("panorama_search", "q2"),
        "  ...  ",
    ]
    agent.llm.chat.return_value = "Final Answer: Recovered section content from prior tool evidence."
    agent._execute_tool = MagicMock(return_value="tool result")

    result = agent._generate_section_react(ReportSection("Section 1"), _make_outline(), [])
    if result == "Recovered section content from prior tool evidence." and agent.llm.chat.call_count == 1:
        ok("T1 - direct-adoption whitespace/ellipsis recovers")
    else:
        fail("T1", f"Unexpected result={result!r}, llm.chat calls={agent.llm.chat.call_count}")



def test_t2_empty_final_answer_recovery():
    agent = _make_agent()
    agent.boost_llm.chat.side_effect = [
        _tool_call("quick_search", "q1"),
        _tool_call("panorama_search", "q2"),
        "Final Answer:   ",
    ]
    agent.llm.chat.return_value = "Final Answer: Recovery after empty Final Answer succeeded."
    agent._execute_tool = MagicMock(return_value="tool result")

    result = agent._generate_section_react(ReportSection("Section 1"), _make_outline(), [])
    if result == "Recovery after empty Final Answer succeeded." and agent.llm.chat.call_count == 1:
        ok("T2 - empty Final Answer gets one recovery attempt")
    else:
        fail("T2", f"Unexpected result={result!r}, llm.chat calls={agent.llm.chat.call_count}")



def test_t3_failed_recovery_still_raises():
    agent = _make_agent()
    agent.boost_llm.chat.side_effect = [
        _tool_call("quick_search", "q1"),
        _tool_call("panorama_search", "q2"),
        "...",
    ]
    agent.llm.chat.return_value = "Final Answer: [omitted]"
    agent._execute_tool = MagicMock(return_value="tool result")

    try:
        agent._generate_section_react(ReportSection("Section 1"), _make_outline(), [])
        fail("T3", "Expected ReportGenerationError but got success")
    except ReportGenerationError as e:
        if e.error_type == "empty_section_content" and e.retryable and agent.llm.chat.call_count == 1:
            ok("T3 - failed recovery still raises retryable empty_section_content")
        else:
            fail("T3", f"Wrong error metadata: type={e.error_type}, retryable={e.retryable}")
    except Exception as e:
        fail("T3", f"Unexpected exception: {type(e).__name__}: {e}")



def test_t4_valid_content_no_regression():
    agent = _make_agent()
    agent.boost_llm.chat.side_effect = [
        _tool_call("quick_search", "q1"),
        _tool_call("panorama_search", "q2"),
        "Final Answer: This is already valid content.",
    ]
    agent._execute_tool = MagicMock(return_value="tool result")

    result = agent._generate_section_react(ReportSection("Section 1"), _make_outline(), [])
    if result == "This is already valid content." and agent.llm.chat.call_count == 0:
        ok("T4 - valid content path still works without recovery")
    else:
        fail("T4", f"Unexpected result={result!r}, llm.chat calls={agent.llm.chat.call_count}")



def test_t5_force_final_recovery():
    agent = _make_agent()
    agent.boost_llm.chat.side_effect = ["thinking..."] * 4
    agent.llm.chat.side_effect = [
        "Final Answer: ...",
        "Final Answer: Recovered after invalid force-final output.",
    ]
    agent._execute_tool = MagicMock(return_value="tool result")

    result = agent._generate_section_react(ReportSection("Section 1"), _make_outline(), [])
    if result == "Recovered after invalid force-final output." and agent.llm.chat.call_count == 2:
        ok("T5 - invalid force-final output gets one recovery attempt")
    else:
        fail("T5", f"Unexpected result={result!r}, llm.chat calls={agent.llm.chat.call_count}")


if __name__ == "__main__":
    tests = [
        test_t1_direct_adoption_recovery,
        test_t2_empty_final_answer_recovery,
        test_t3_failed_recovery_still_raises,
        test_t4_valid_content_no_regression,
        test_t5_force_final_recovery,
    ]

    print("Running focused empty-response recovery validation...\n")
    for test in tests:
        test()

    print(f"\nSummary: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        sys.exit(1)
