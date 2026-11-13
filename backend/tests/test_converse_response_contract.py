"""Regression tests for Converse response-quality instructions.

These tests check the shared generation contract for JSON and streaming.
They do not claim that a live LLM obeys every instruction.
"""
from app.services import chat_service


def test_converse_instructions_prioritize_user_request_and_language():
    instructions = chat_service._NORMAL_CHAT_INSTRUCTIONS
    assert "Determine the actual task and answer it" in instructions
    assert "Follow the user's requested format, length, and language" in instructions
    assert "Bangla, Japanese, and English" in instructions


def test_converse_instructions_prevent_fabricated_capabilities():
    instructions = chat_service._NORMAL_CHAT_INSTRUCTIONS
    assert "Never fabricate a source, tool result, citation" in instructions
    assert "do not\n  imply the answer was checked online" in instructions
    assert "the current user message is authoritative" in instructions.lower()


def test_converse_streaming_and_json_share_instruction_contract():
    """Both entrypoints intentionally use the same instructions."""
    import inspect

    for endpoint in (
        chat_service.generate_normal_chat_reply,
        chat_service.stream_normal_chat_reply,
    ):
        source = inspect.getsource(endpoint)
        assert "_NORMAL_CHAT_INSTRUCTIONS" in source
