"""Deterministic arithmetic for ordinary text and speech, without eval/network.

Only explicit short, unambiguous calculations are handled. Other questions
go through the existing full chat/RAG/web brain unchanged. Bounded inputs
prevent resource-exhausting expressions and accidental tool execution.
"""
from __future__ import annotations

import ast
import re
import unicodedata
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext


_SPOKEN_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
    "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20",
}
_OPERATORS = [
    (r"\\bdivided by\\b|\\bover\\b|ভাগ|わる|割る", "/"),
    (r"\\bmultiplied by\\b|\\btimes\\b|গুণ|かける|掛ける", "*"),
    (r"\\bplus\\b|যোগ|たす|足す", "+"),
    (r"\\bminus\\b|বিয়োগ|বিয়োগ|ひく|引く", "-"),
]
_PREFIX = re.compile(
    r"^(?:what(?:'s| is)|calculate|compute|how much is|"
    r"please calculate|work out|please work out|"
    r"কত হবে|হিসাব করো|কত|計算して|いくらですか)\\s*",
    re.IGNORECASE,
)
_SUFFIX = re.compile(
    r"\\s*(?:equals?|equal to|কত|কত হবে|"
    r"হিসাব করো|はいくつ|は何|ですか|は|?)\\s*$",
    re.IGNORECASE,
)
_SAFE_CHARACTERS = re.compile(r"[0-9.+\\-*/()% \\t]+\\Z")
_LIMIT = Decimal("1000000000000")


class ArithmeticOutOfScope(ValueError):
    """Not a small arithmetic expression; defer to the real LLM."""


def _evaluate(node: ast.AST, depth: int = 0) -> Decimal:
    if depth > 12:
        raise ArithmeticOutOfScope
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, depth + 1)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        value = Decimal(str(node.value))
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        child = _evaluate(node.operand, depth + 1)
        value = child if isinstance(node.op, ast.UAdd) else -child
    elif isinstance(node, ast.BinOp):
        left = _evaluate(node.left, depth + 1)
        right = _evaluate(node.right, depth + 1)
        op = node.op
        if isinstance(op, ast.Add):
            value = left + right
        elif isinstance(op, ast.Sub):
            value = left - right
        elif isinstance(op, ast.Mult):
            value = left * right
        elif isinstance(op, ast.Div):
            value = left / right
        elif isinstance(op, ast.Mod):
            value = left % right
        elif isinstance(op, ast.Pow):
            if abs(right) > 8 or right != right.to_integral_value() or abs(left) > 1000000:
                raise ArithmeticOutOfScope
            value = left ** int(right)
        else:
            raise ArithmeticOutOfScope
    else:
        raise ArithmeticOutOfScope
    if not value.is_finite() or abs(value) > _LIMIT:
        raise ArithmeticOutOfScope
    return value


def exact_calculation_reply(message: str) -> str | None:
    """Solve explicit arithmetic exactly; never intercept narrative questions."""
    if not message or len(message) > 180:
        return None
    text = unicodedata.normalize("NFKC", message).strip()
    # Bengali/Arabic numerals are normalized without changing spoken language.
    text = "".join(str(unicodedata.digit(ch)) if ch.isdecimal() else ch for ch in text)
    original = text
    text = text.casefold().rstrip("?？。!। ").strip()
    text = _PREFIX.sub("", text).strip()
    text = _SUFFIX.sub("", text).strip()
    for pattern, operator in _OPERATORS:
        text = re.sub(pattern, f" {operator} ", text, flags=re.IGNORECASE)
    for word, numeral in _SPOKEN_NUMBERS.items():
        text = re.sub(rf"\\b{word}\\b", numeral, text)
    text = text.replace("×", "*").replace("÷", "/").replace("−", "-")
    # Many speech transcripts say "2 to the power of 3".
    text = re.sub(r"\\bto the power of\\b", " ** ", text)
    if not _SAFE_CHARACTERS.fullmatch(text):
        return None
    if not re.search(r"[+*/%\\-]", text) or not re.search(r"\\d", text):
        return None
    if len(text) > 100 or re.search(r"\\*{3,}|/{2,}", text):
        return None
    try:
        with localcontext() as ctx:
            ctx.prec = 30
            value = _evaluate(ast.parse(text, mode="eval"))
    except (SyntaxError, ArithmeticOutOfScope, InvalidOperation, DivisionByZero, ZeroDivisionError):
        return None
    number = format(value.normalize(), "f")
    if len(number) > 45:
        return None
    if any("\\u0980" <= ch <= "\\u09ff" for ch in original):
        return f"উত্তর: {number}।"
    if any("\\u3040" <= ch <= "\\u30ff" or "\\u3400" <= ch <= "\\u9fff" for ch in original):
        return f"答えは{number}です。"
    return f"The answer is {number}."
