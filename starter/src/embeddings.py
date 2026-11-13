"""Real local embedding model (Sentence Transformers). No mock/random fallback: any failure raises."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    """paraphrase-multilingual-MiniLM-L12-v2: symmetric model, same encoding for queries and documents,
    L2-normalised so cosine distance == 1 - dot product."""

    def __init__(self, model_name: str, expected_dims: int | None = None) -> None:
        from sentence_transformers import SentenceTransformer  # ImportError/OSError propagate on purpose
        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device="cpu")
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dimensions = int(get_dim())
        if expected_dims is not None and self.dimensions != expected_dims:
            raise ValueError(f"{model_name} returns {self.dimensions} dims, expected {expected_dims}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
        if len(vecs) != len(texts):
            raise RuntimeError("embedder returned a different number of vectors than inputs")
        return [v.tolist() for v in vecs]

    def embed_query(self, question: str) -> list[float]:
        return self.embed_documents([question])[0]
