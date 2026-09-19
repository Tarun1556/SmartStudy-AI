from abc import ABC, abstractmethod
import hashlib
import math
from typing import List, Optional
import re
import logging

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...

    @abstractmethod
    def dimension(self) -> int:
        ...


class MockEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 384):
        self._dim = dim

    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            vec = self._embed_one(text)
            results.append(vec)
        return results

    def _embed_one(self, text: str) -> List[float]:
        dim = self._dim
        tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
        vec = [0.0] * dim
        if not tokens:
            vec[0] = 1.0
            return self._normalize(vec)

        for tok in tokens:
            h = hashlib.md5(tok.encode()).digest()
            for i in range(0, min(16, dim // 2)):
                idx1 = (h[i] * 131 + i * 7) % dim
                idx2 = (h[i] * 17 + i * 31 + 3) % dim
                val = (h[i] / 255.0) * 0.1 + 0.01
                vec[idx1] += val
                vec[idx2] -= val * 0.5

        words = set(tokens)
        for i, w in enumerate(sorted(words)):
            idx = (hash(w) & 0x7FFFFFFF) % dim
            vec[idx] += 0.05

        return self._normalize(vec)

    @staticmethod
    def _normalize(vec: List[float]) -> List[float]:
        s = sum(v * v for v in vec) ** 0.5
        if s < 1e-12:
            v = list(vec)
            v[0] = 1.0
            return v
        return [v / s for v in vec]


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str, expected_dim: int = 384):
        self.model_name = model_name
        self.expected_dim = expected_dim
        self._model = None
        self._dim = expected_dim
        self._load_attempted = False
        self._load_failed = False
        self._fallback: Optional[MockEmbeddingProvider] = None

    def _fallback_provider(self) -> MockEmbeddingProvider:
        if self._fallback is None:
            self._fallback = MockEmbeddingProvider(self._dim)
        return self._fallback

    def _load(self) -> bool:
        if self._load_attempted:
            return not self._load_failed
        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            actual_dim = self._model.get_sentence_embedding_dimension() or self.expected_dim
            self._dim = int(actual_dim)
            if self._dim != self.expected_dim:
                logger.warning(
                    "SentenceTransformer model %s produced embedding dimension %d, "
                    "but schema expects %d. Falling back to Mock embeddings.",
                    self.model_name, self._dim, self.expected_dim,
                )
                self._model = None
                self._load_failed = True
                return False
            logger.info("Loaded SentenceTransformer model: %s (dim=%d)", self.model_name, self._dim)
            return True
        except Exception as e:
            logger.warning(
                "Failed to load SentenceTransformer model %s: %s. "
                "Falling back to MockEmbeddingProvider (dim=%d).",
                self.model_name, e, self.expected_dim,
            )
            self._load_failed = True
            self._model = None
            return False

    def dimension(self) -> int:
        if self._model is None:
            self._load()
        return self._dim

    @property
    def is_loaded(self) -> bool:
        if not self._load_attempted:
            self._load()
        return self._model is not None and not self._load_failed

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self._load_attempted:
            self._load()
        if not self._model:
            return self._fallback_provider().embed_texts(texts)
        try:
            arr = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            result = []
            for v in arr:
                vec = [float(x) for x in v.tolist()]
                if len(vec) != self._dim:
                    padded = [0.0] * self._dim
                    for i in range(min(len(vec), self._dim)):
                        padded[i] = vec[i]
                    result.append(MockEmbeddingProvider._normalize(padded))
                else:
                    result.append(vec)
            return result
        except Exception as e:
            logger.warning("SentenceTransformer.encode failed: %s. Falling back.", e)
            return self._fallback_provider().embed_texts(texts)


def _have_sentence_transformers() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


_provider: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider

    prov = settings.EMBEDDING_PROVIDER.lower() if settings.EMBEDDING_PROVIDER else "mock"
    want_real = prov in ("sentence_transformers", "st", "auto")

    if want_real:
        if _have_sentence_transformers():
            try:
                st_provider = SentenceTransformerProvider(settings.SENTENCE_TRANSFORMERS_MODEL, expected_dim=384)
                if st_provider.is_loaded and st_provider.dimension() == 384:
                    _provider = st_provider
                    return _provider
                logger.warning(
                    "SentenceTransformer not usable (loaded=%s, dim=%d, expected=384); using MockEmbeddingProvider.",
                    getattr(st_provider, "is_loaded", False), st_provider.dimension(),
                )
            except Exception as e:
                logger.warning("Failed to instantiate SentenceTransformerProvider: %s", e)

    _provider = MockEmbeddingProvider(384)
    if want_real:
        logger.info(
            "Using MockEmbeddingProvider (EMBEDDING_PROVIDER=%s but sentence_transformers package unavailable). "
            "Install with: pip install sentence-transformers",
            settings.EMBEDDING_PROVIDER,
        )
    return _provider


def cosine_similarity(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    # `a`/`b` may be plain Python lists or numpy arrays (pgvector's SQLAlchemy
    # Vector type deserializes DB-loaded columns as numpy.ndarray). `bool()`/`not`
    # on a multi-element ndarray raises "truth value of an array ... is ambiguous",
    # so length/emptiness must be checked without applying `not`/`if array:` to it.
    if a is None or b is None:
        return 0.0
    a = a.tolist() if hasattr(a, "tolist") else list(a)
    b = b.tolist() if hasattr(b, "tolist") else list(b)
    if len(a) == 0 or len(b) == 0 or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
