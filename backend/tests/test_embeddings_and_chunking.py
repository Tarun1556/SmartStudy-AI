"""Fast, deterministic unit tests for the retrieval building blocks: cosine
similarity scoring and the text chunker used before embedding. No DB, no
network — these are the pieces search_hybrid and the background job's
notes/topic pipeline depend on, and they're cheap to get right in isolation.
"""
import math

from app.services.embeddings import cosine_similarity, MockEmbeddingProvider
from app.services.ingestion.chunking import chunk_text


def test_cosine_similarity_identical_vectors_is_one():
    v = [0.1, 0.2, 0.3, 0.4]
    assert math.isclose(cosine_similarity(v, v), 1.0, rel_tol=1e-6)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert math.isclose(cosine_similarity(a, b), 0.0, abs_tol=1e-9)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert math.isclose(cosine_similarity(a, b), -1.0, rel_tol=1e-6)


def test_cosine_similarity_handles_none_inputs():
    assert cosine_similarity(None, [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], None) == 0.0
    assert cosine_similarity(None, None) == 0.0


def test_cosine_similarity_handles_mismatched_length():
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_cosine_similarity_handles_empty_vectors():
    assert cosine_similarity([], []) == 0.0


def test_cosine_similarity_handles_zero_vector():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_accepts_numpy_like_arrays():
    class _FakeArray:
        """Mimics the numpy.ndarray pgvector returns from a loaded row: has
        .tolist() but raising on bool()/len() the way a multi-element ndarray
        does is what previously broke naive `if vec:` checks."""
        def __init__(self, data):
            self._data = data

        def tolist(self):
            return list(self._data)

    a = _FakeArray([1.0, 0.0])
    b = _FakeArray([1.0, 0.0])
    assert math.isclose(cosine_similarity(a, b), 1.0, rel_tol=1e-6)


def test_mock_embedding_provider_is_deterministic_and_normalized():
    prov = MockEmbeddingProvider(dim=64)
    v1 = prov.embed_texts(["binary search tree"])[0]
    v2 = prov.embed_texts(["binary search tree"])[0]
    assert v1 == v2
    norm = sum(x * x for x in v1) ** 0.5
    assert math.isclose(norm, 1.0, rel_tol=1e-6)


def test_mock_embedding_provider_differentiates_distinct_text():
    prov = MockEmbeddingProvider(dim=64)
    a = prov.embed_texts(["binary search tree traversal"])[0]
    b = prov.embed_texts(["quarterly revenue forecast model"])[0]
    assert cosine_similarity(a, a) > cosine_similarity(a, b)


def test_chunk_text_empty_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text(None) == []


def test_chunk_text_short_text_returns_single_chunk():
    text = "A short sentence that fits in one chunk."
    chunks = chunk_text(text, chunk_size=400, overlap=80)
    assert chunks == [text]


def test_chunk_text_long_text_splits_with_overlap():
    sentence = "The quick brown fox jumps over the lazy dog. "
    text = sentence * 40  # well over chunk_size
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 260  # chunk_size + a little slack for sentence boundaries
    # Overlap: the tail of one chunk should reappear near the start of the next.
    assert chunks[0][-20:] in chunks[1] or chunks[1].startswith(chunks[0][-50:].split(" ", 1)[-1][:20])


def test_chunk_text_normalizes_whitespace():
    text = "Line one.\n\n\tLine   two.\nLine three."
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert "\n" not in chunks[0]
    assert "\t" not in chunks[0]
