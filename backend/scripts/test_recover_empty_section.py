"""
Offline validation for the no-tool recovery patch in _generate_section_react.

Tests:
  T1 - whitespace/ellipsis direct-adoption: recovery is called, recovered content adopted
  T2 - empty Final Answer: recovery is called, recovered content adopted
  T3 - recovery still placeholder: ReportGenerationError raised (retryable)
  T4 - valid content regression: no recovery called, content returned directly

All tests run without network calls.
"""

import sys
import os
from unittest.mock import MagicMock, patch

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


# ── import the relevant pieces ───────────────────────────────────────────────

from app.services.report_agent import ReportAgent, ReportGenerationError


def _make_agent():
    """Return a ReportAgent with all external dependencies mocked out."""
    agent = ReportAgent.__new__(ReportAgent)

    agent.report_logger = None
    agent.simulation_requirement = "test sim"
    agent.MAX_TOOL_CALLS_PER_SECTION = 6
    agent.boost_llm = MagicMock()
    agent.llm = MagicMock()
    agent.tools = {}
    return agent


def _make_section(title="Test Section"):
    sec = MagicMock()
    sec.title = title
    return sec


def _make_outline(title="Test Report", summary="summary"):
    ol = MagicMock()
    ol.title = title
    ol.summary = summary
    return ol


# ── T1: whitespace/ellipsis direct-adoption path → recovery succeeds ─────────

def test_t1_direct_adoption_whitespace_recovered():
    """
    Scenario: tool calls done, LLM outputs whitespace-only (no Final Answer prefix).
    Direct-adoption branch triggers; _recover_section_content returns real prose.
    Expect: recovered content returned, no exception.
    """
    agent = _make_agent()
    section = _make_section("T1 Section")
    outline = _make_outline()

    RECOVERED = "Recovered prose for the section with real content here."

    # First two iterations: tool calls (so min_tool_calls satisfied)
    # Third iteration: whitespace-only, no tool calls, no Final Answer
    responses = [
        "<tool_call>\n{\"name\": \"quick_search\", \"parameters\": {\"query\": \"x\"}}\n</tool_call>",
        "<tool_call>\n{\"name\": \"panorama_search\", \"parameters\": {\"query\": \"y\"}}\n</tool_call>",
        "   \t  ",  # whitespace-only → triggers recovery
    ]

    agent.boost_llm.chat = MagicMock(side_effect=responses)
    agent._execute_tool = MagicMock(return_value="tool result")
    agent._recover_section_content = MagicMock(return_value=RECOVERED)

    result = agent._generate_section_react(section, outline, [])

    assert result == RECOVERED, f"Expected recovered content, got: {repr(result)}"
    agent._recover_section_content.assert_called_once()
    ok("T1 whitespace direct-adoption recovered")


# ── T2: empty Final Answer → recovery succeeds ───────────────────────────────

def test_t2_empty_final_answer_recovered():
    """
    Scenario: after tool calls, LLM outputs 'Final Answer:' with nothing after it.
    Expect: recovery called, recovered content returned.
    """
    agent = _make_agent()
    section = _make_section("T2 Section")
    outline = _make_outline()

    RECOVERED = "Substantive recovered content for T2."

    responses = [
        "<tool_call>\n{\"name\": \"quick_search\", \"parameters\": {\"query\": \"a\"}}\n</tool_call>",
        "<tool_call>\n{\"name\": \"insight_forge\", \"parameters\": {\"question\": \"b\"}}\n</tool_call>",
        "Final Answer:",  # empty after split
    ]

    agent.boost_llm.chat = MagicMock(side_effect=responses)
    agent._execute_tool = MagicMock(return_value="tool result")
    agent._recover_section_content = MagicMock(return_value=RECOVERED)

    result = agent._generate_section_react(section, outline, [])

    assert result == RECOVERED, f"Expected recovered content, got: {repr(result)}"
    agent._recover_section_content.assert_called_once()
    ok("T2 empty Final Answer recovered")


# ── T3: recovery still returns placeholder → error raised ────────────────────

def test_t3_recovery_still_placeholder_raises():
    """
    Scenario: Final Answer is empty AND recovery also returns None.
    Expect: ReportGenerationError with retryable=True.
    """
    agent = _make_agent()
    section = _make_section("T3 Section")
    outline = _make_outline()

    responses = [
        "<tool_call>\n{\"name\": \"quick_search\", \"parameters\": {\"query\": \"c\"}}\n</tool_call>",
        "<tool_call>\n{\"name\": \"panorama_search\", \"parameters\": {\"query\": \"d\"}}\n</tool_call>",
        "Final Answer:",  # empty
    ]

    agent.boost_llm.chat = MagicMock(side_effect=responses)
    agent._execute_tool = MagicMock(return_value="tool result")
    agent._recover_section_content = MagicMock(return_value=None)  # recovery fails

    raised = False
    try:
        agent._generate_section_react(section, outline, [])
    except ReportGenerationError as e:
        raised = True
        assert e.retryable is True, f"Expected retryable=True, got {e.retryable}"
        assert e.error_type == "empty_section_content", f"Wrong error_type: {e.error_type}"
        assert e.section_title == "T3 Section", f"Wrong section_title: {e.section_title}"
        assert e.section_index == 0, f"Wrong section_index: {e.section_index}"

    assert raised, "Expected ReportGenerationError to be raised"
    agent._recover_section_content.assert_called_once()
    ok("T3 recovery still placeholder raises retryable error")


# ── T4: valid content regression ─────────────────────────────────────────────

def test_t4_valid_content_no_recovery():
    """
    Scenario: LLM produces a proper Final Answer with substantive content.
    Expect: content returned directly, _recover_section_content never called.
    """
    agent = _make_agent()
    section = _make_section("T4 Section")
    outline = _make_outline()

    CONTENT = "This is a well-written section with multiple sentences of real analysis."

    responses = [
        "<tool_call>\n{\"name\": \"quick_search\", \"parameters\": {\"query\": \"e\"}}\n</tool_call>",
        "<tool_call>\n{\"name\": \"interview_agents\", \"parameters\": {\"agents\": [\"expert\"]}}\n</tool_call>",
        f"Final Answer:\n{CONTENT}",
    ]

    agent.boost_llm.chat = MagicMock(side_effect=responses)
    agent._execute_tool = MagicMock(return_value="tool result")
    agent._recover_section_content = MagicMock()  # should NOT be called

    result = agent._generate_section_react(section, outline, [])

    assert result == CONTENT, f"Expected valid content, got: {repr(result)}"
    agent._recover_section_content.assert_not_called()
    ok("T4 valid content returned without recovery")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running recovery patch validation...\n")

    for test_fn in [
        test_t1_direct_adoption_whitespace_recovered,
        test_t2_empty_final_answer_recovered,
        test_t3_recovery_still_placeholder_raises,
        test_t4_valid_content_no_recovery,
    ]:
        try:
            test_fn()
        except Exception as exc:
            name = test_fn.__name__
            fail(name, str(exc))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
