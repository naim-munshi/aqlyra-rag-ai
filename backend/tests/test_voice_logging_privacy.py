"""Guard against logging private voice transcripts or user text."""

import ast
from pathlib import Path


VOICE_WORKER = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "voice"
    / "worker.py"
)


def test_voice_logger_never_receives_raw_user_text() -> None:
    tree = ast.parse(VOICE_WORKER.read_text(encoding="utf-8"))
    log_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
        and node.func.attr in {
            "debug",
            "info",
            "warning",
            "error",
            "exception",
            "critical",
        }
    ]

    assert log_calls, "Expected to inspect voice worker log calls"

    for call in log_calls:
        for argument in (*call.args, *[kw.value for kw in call.keywords]):
            for expression in ast.walk(argument):
                assert not (
                    isinstance(expression, ast.Name)
                    and expression.id == "user_text"
                ), "Voice logs must not contain user text"

                assert not (
                    isinstance(expression, ast.Attribute)
                    and expression.attr == "transcript"
                    and isinstance(expression.value, ast.Name)
                    and expression.value.id == "event"
                ), "Voice logs must not contain user transcripts"


def test_voice_provider_errors_do_not_log_sensitive_tracebacks() -> None:
    source = VOICE_WORKER.read_text(encoding="utf-8")
    assert "logger.exception(" not in source
    assert "voice_llm_node_failed exception_type=%s" in source
