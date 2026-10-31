"""Tenant-safe lexical recall when semantic memory embeddings are unavailable.

No fake vector similarity. Memory text is not document evidence.
Scans a fixed number of active owned memories and only returns relevant
literal overlaps; ignores unrelated personal details and secret-like texts.
"""
import re
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.memory import Memory
from app.services.memory_retrieval_service import MemoryRetrievalHit

_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset({
    "what", "when", "where", "who", "the", "that", "this", "how",
    "about", "please", "tell", "give", "your", "you", "have",
    "does", "which", "want", "can", "is", "are", "my", "our",
    "আমি", "আমার", "কি", "কী", "কত", "বলো", "দাও", "এবং",
    "私", "の", "は", "です", "について",
})
_SECRET = re.compile(
    r"(?i)(?:password|passcode|api[_ -]?key|bearer|otp|"
    r"secret|access[_ -]?token|refresh[_ -]?token)"
)


def _terms(text: str) -> set[str]:
    words = _WORDS.findall(text.casefold()[:1024])
    result: set[str] = set()
    for word in words[:96]:
        if word in _STOP or len(word) < 2:
            continue
        result.add(word)
        # Long Japanese/Bangla tokens need small overlapping substrings.
        if len(word) >= 4 and any(ord(c) > 127 for c in word):
            result.update(word[i : i + 3] for i in range(len(word) - 2))
    return result


def retrieve_lexical_memories_for_user(
    *, db: Session, user_id: str, query_text: str,
    top_k: int = 5, scan_limit: int = 120,
) -> list[MemoryRetrievalHit]:
    if not user_id.strip() or not query_text.strip():
        return []
    if not 1 <= top_k <= 20 or not 1 <= scan_limit <= 200:
        raise ValueError("Invalid bounded memory retrieval limits")
    question = _terms(query_text)
    if not question:
        return []
    statement = (
        select(Memory)
        .where(Memory.user_id == user_id, Memory.is_active.is_(True))
        .order_by(Memory.updated_at.desc(), Memory.id.desc())
        .limit(scan_limit)
    )
    ranked: list[tuple[float, Memory]] = []
    for memory in db.scalars(statement):
        if _SECRET.search(memory.content):
            continue
        words = _terms(memory.content)
        overlap = len(question & words)
        if not overlap:
            continue
        score = overlap / max(len(question), 1)
        ranked.append((
            score * 0.85 + float(memory.importance) * 0.10
            + float(memory.confidence) * 0.05, memory
        ))
    ranked.sort(key=lambda item: (-item[0], -item[1].importance, item[1].id))
    return [
        MemoryRetrievalHit(
            memory_id=memory.id,
            kind=memory.kind,
            content=memory.content[:600],
            importance=memory.importance,
            confidence=memory.confidence,
            similarity_score=score,
            cosine_distance=None,
            retrieval_mode="lexical",
        )
        for score, memory in ranked[:top_k]
    ]
