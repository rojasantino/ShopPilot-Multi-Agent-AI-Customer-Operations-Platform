"""Text -> vector. Two interchangeable embedders (same 384 dimensions)."""

import hashlib
import math
import re
from typing import Protocol

from app.core.config import Settings

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an the and or of to in on for is are was were be it its this that with as at by from "
    "i you we my your our can do does how what when where which will would should".split()
)


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Dependency-free 'feature hashing' embedder: lexical, deterministic, great for tests/demo."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _tokens(self, text: str) -> list[str]:
        words = [w for w in _TOKEN.findall(text.lower()) if w not in _STOP]
        return words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in self._tokens(text):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class SentenceTransformerEmbedder:
    """Real semantic embeddings (BAAI/bge-small-en-v1.5 -> 384 dims). Needs requirements-ml.txt."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, keep lazy

        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def build_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "sentence-transformers":
        embedder: Embedder = SentenceTransformerEmbedder(settings.embedding_model)
        if embedder.dim != settings.embedding_dim:
            raise ValueError(
                f"Model dim {embedder.dim} != EMBEDDING_DIM {settings.embedding_dim}; "
                "the pgvector column size must match."
            )
        return embedder
    return HashEmbedder(settings.embedding_dim)
