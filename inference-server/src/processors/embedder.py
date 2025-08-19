"""Embedding utilities built on top of LangChain."""

from typing import List

from config import OPENAI_API_KEY, EMBEDDING_MODEL

# LangChain recently moved the OpenAI wrappers into a separate package.  We try
# to import from ``langchain_openai`` first and fall back to the legacy location
# for older versions.  This keeps the code compatible with a wider range of
# LangChain releases.
try:  # pragma: no cover - exercised in tests via patching
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover
    from langchain.embeddings.openai import OpenAIEmbeddings  # type: ignore


class Embedder:
    """Generate embeddings using LangChain's ``OpenAIEmbeddings`` wrapper."""

    def __init__(self) -> None:
        self.client = OpenAIEmbeddings(
            model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts and return the raw vectors."""
        return self.client.embed_documents(texts)
