"""Vector store abstractions.

The project aims to support both a simple in-memory store for testing and a
Weaviate-backed implementation for production.  Only the in-memory store is
used in the tests, but the Weaviate wrapper remains for parity with the
README's architecture description.
"""

import weaviate
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np


class WeaviateVectorStore:
    """Minimal wrapper around a Weaviate collection.

    The store supports adding plain text documents with optional metadata and
    hybrid similarity search combining BM25 and semantic vectors.
    """

    def __init__(
        self,
        client: weaviate.Client,
        index_name: str = "Document",
        text_key: str = "text",
        embedding: Optional[Callable[[str], List[float]]] = None,
    ) -> None:
        self.client = client
        self.index_name = index_name
        self.text_key = text_key
        self.embedding = embedding
        self._ensure_schema()

    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        """Create the schema for the index if it does not already exist."""
        schema = {
            "class": self.index_name,
            "vectorizer": "none",
            "properties": [
                {"name": self.text_key, "dataType": ["text"]},
                {"name": "chunk_id", "dataType": ["text"]},
                {"name": "doc_uid", "dataType": ["text"]},
                {"name": "order_index", "dataType": ["int"]},
                {"name": "type", "dataType": ["text"]},
            ],
        }
        if not self.client.schema.exists(self.index_name):
            self.client.schema.create_class(schema)
        
        # Update index_name to match Weaviate's actual class name (which may be capitalized)
        actual_classes = [cls['class'] for cls in self.client.schema.get().get('classes', [])]
        for class_name in actual_classes:
            if class_name.lower() == self.index_name.lower():
                self.index_name = class_name  # Use the actual capitalized name
                break

    # ------------------------------------------------------------------
    def add_texts(
        self,
        texts: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add a batch of texts with optional metadata to the store."""

        metadatas = metadatas or [{} for _ in texts]
        with self.client.batch as batch:
            batch.batch_size = 100
            for i, (text, metadata) in enumerate(zip(texts, metadatas)):
                if embeddings is not None:
                    vector = embeddings[i]
                else:
                    vector = self.embedding(text) if self.embedding else None
                obj = {self.text_key: text, **metadata}
                batch.add_data_object(obj, self.index_name, vector=vector)

    # ------------------------------------------------------------------
    def similarity_search(
        self,
        query: str,
        k: int = 4,
        alpha: float = 0.5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return the top ``k`` most similar documents for ``query``.

        The search is "hybrid" -- it combines BM25 keyword search with
        semantic vector search.  The ``alpha`` parameter controls the weighting
        between the two methods (0 = only keyword, 1 = only vector).
        """
        vector = self.embedding(query) if self.embedding else None
        query_builder = (
            self.client.query
            .get(self.index_name, [self.text_key, "chunk_id", "doc_uid", "order_index", "type"])
            .with_hybrid(query, vector=vector, alpha=alpha)
            .with_additional(["score"])
        )
        
        # Add filter if provided
        if filter:
            query_builder = query_builder.with_where(filter)
            
        result = query_builder.with_limit(k).do()
        hits = result.get("data", {}).get("Get", {}).get(self.index_name, [])
        # Format results as a list of documents with text and metadata
        documents: List[Dict[str, Any]] = []
        for hit in hits:
            doc = {
                "text": hit.get(self.text_key, ""),
                "score": hit.get("_additional", {}).get("score", 0.0)  # Get hybrid score
            }
            # Include all metadata fields
            for key, value in hit.items():
                if key not in [self.text_key, "_additional"]:
                    doc[key] = value
            documents.append(doc)
        return documents


class SimpleVectorStore:
    """A minimal in-memory vector store used for tests and examples.

    The store keeps a list of texts alongside their corresponding embedding
    vectors.  Similarity search is performed using cosine similarity.
    """

    def __init__(self) -> None:
        self.texts: List[str] = []
        self.embeddings: List[List[float]] = []

    # ------------------------------------------------------------------
    def add_texts(self, texts: List[str], embeddings: List[List[float]]) -> None:
        """Add texts with precomputed embeddings to the store."""

        self.texts.extend(texts)
        self.embeddings.extend(embeddings)

    # ------------------------------------------------------------------
    def similarity_search(
        self, query_embedding: List[float], k: int = 4
    ) -> List[Tuple[str, float]]:
        """Return the ``k`` most similar texts for ``query_embedding``."""

        if not self.embeddings:
            return []

        q = np.array(query_embedding)
        scores: List[Tuple[str, float]] = []
        for text, emb in zip(self.texts, self.embeddings):
            e = np.array(emb)
            score = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-10))
            scores.append((text, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]

def get_vector_store(
    embed_fn: Callable[[List[str]], List[List[float]]]
) -> Union[WeaviateVectorStore, SimpleVectorStore]:
    """Instantiate a vector store, preferring Weaviate if available.

    The function tries to create a ``WeaviateVectorStore`` using configuration
    values from :mod:`config`.  If the connection fails for any reason the
    function falls back to the in-memory :class:`SimpleVectorStore` so that the
    rest of the system remains usable.
    """

    from config import COLLECTION_NAME, WEAVIATE_API_KEY, WEAVIATE_URL

    try:  # pragma: no cover - requires external service
        auth = (
            weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY)
            if WEAVIATE_API_KEY
            else None
        )
        client = weaviate.Client(url=WEAVIATE_URL, auth_client_secret=auth, timeout_config=(2, 2))
        return WeaviateVectorStore(
            client,
            index_name=COLLECTION_NAME,
            embedding=lambda text: embed_fn([text])[0],
        )
    except Exception:
        return SimpleVectorStore()
