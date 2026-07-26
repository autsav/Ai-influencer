from unittest.mock import MagicMock, patch

from aeloria.optimizer.analyst import DATA_ANALYZER_PROMPT, analyze


def _settings(enabled, key="sk"):
    s = MagicMock(); s.optimizer_analyst_enabled = enabled
    return s


def test_prompt_deliverable_covers_the_sections():
    for token in ("TOP DRIVERS", "UNDERPERFORMERS", "AUDIENCE READ", "EXPERIMENTS", "WEIGHT NUDGES"):
        assert token in DATA_ANALYZER_PROMPT
    assert "correlation" in DATA_ANALYZER_PROMPT.lower()


def test_analyze_disabled_returns_empty():
    assert analyze({"n_posts": 5, "dimensions": {}}, 32, [], _settings(False)) == ""


@patch("aeloria.optimizer.analyst.llm_generate")
def test_analyze_enabled_returns_report(mock_llm):
    mock_llm.return_value = "ANALYST REPORT"
    out = analyze({"n_posts": 20, "dimensions": {"content_format": {"reel": {"lift": 1.4, "n": 6}}}},
                  1200, ["off-brand"], _settings(True))
    assert out == "ANALYST REPORT"
    prompt = mock_llm.call_args.args[0]
    assert "1200" in prompt and "reel" in prompt


@patch("aeloria.optimizer.analyst.llm_generate", side_effect=Exception("down"))
def test_analyze_llm_failure_returns_empty(_m):
    assert analyze({"n_posts": 20, "dimensions": {}}, 1200, [], _settings(True)) == ""