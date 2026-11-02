"""Pure-Python retrieval: PDF -> text -> chunks -> BM25 ranking.
No vector DB, no embeddings, no network. Easy to explain and to unit-test.
(Upgrade path: swap rank_chunks() for pgvector / embedding search.)"""
import math
import re
from collections import Counter

STOPWORDS = set(
    "a an the and or but if of to in on at by for with from as is are was were be been being this that these those "
    "it its into than then so such not no do does did how what which who whom why when where can could should would "
    "will shall may might about over under between also have has had i you he she we they them his her our your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


def chunk_text(text: str, words_per_chunk: int = 150, overlap: int = 30) -> list[str]:
    """Sliding window over words. Overlap keeps sentences that straddle a boundary retrievable."""
    if overlap >= words_per_chunk:
        raise ValueError("overlap must be smaller than words_per_chunk")
    words = text.split()
    step = words_per_chunk - overlap
    chunks = []
    for start in range(0, len(words), step):
        piece = words[start:start + words_per_chunk]
        if piece:
            chunks.append(" ".join(piece))
        if start + words_per_chunk >= len(words):
            break
    return chunks


def rank_chunks(question: str, chunks: list[str], top_k: int = 4, k1: float = 1.5, b: float = 0.75):
    """BM25 scoring. Returns [(chunk_index, score)] best first, only chunks with score > 0."""
    q_terms = set(tokenize(question))
    if not q_terms or not chunks:
        return []
    docs = [Counter(tokenize(c)) for c in chunks]
    n = len(docs)
    avg_len = (sum(sum(d.values()) for d in docs) / n) or 1
    df = {t: sum(1 for d in docs if t in d) for t in q_terms}
    scored = []
    for i, d in enumerate(docs):
        length = sum(d.values())
        score = 0.0
        for t in q_terms:
            if df[t] == 0:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            tf = d[t]
            score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg_len))
        if score > 0:
            scored.append((i, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
