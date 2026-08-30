"""Embedding service for chunks using OpenAI."""

import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


class ReliefEmbedder:
    """Create embeddings for relief chunks using OpenAI API."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """
        Initialize embedder.

        Args:
            api_key: OpenAI API key
            model: Embedding model (text-embedding-3-small or text-embedding-3-large)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        logger.info(f"Embedder initialized with model: {model}")

    def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text chunk.

        Args:
            text: Text to embed

        Returns:
            Vector embedding (1536 dims for small, 3072 for large)
        """
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text provided to embed_text")
            return []

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.data[0].embedding
            logger.debug(f"Embedded text ({len(text)} chars) → {len(embedding)} dims")
            return embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise RuntimeError(f"OpenAI embedding failed: {e}") from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in one call (more efficient).

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings
        """
        if not texts:
            logger.warning("Empty text list provided to embed_batch")
            return []

        # Filter out empty texts
        texts_to_embed = [t for t in texts if t and len(t.strip()) > 0]

        if not texts_to_embed:
            logger.warning("No non-empty texts to embed")
            return []

        logger.info(f"Embedding batch of {len(texts_to_embed)} texts...")

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts_to_embed,
            )

            embeddings = [item.embedding for item in response.data]
            logger.info(f"Embedded {len(embeddings)} texts successfully")
            return embeddings
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            raise RuntimeError(f"OpenAI batch embedding failed: {e}") from e

    def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Embed all chunks and add embeddings to them.

        Args:
            chunks: List of chunk dicts from chunker

        Returns:
            Same chunks with 'embedding' field added
        """
        if not chunks:
            return []

        logger.info(f"Embedding {len(chunks)} chunks...")

        # Extract texts
        texts = [chunk["text"] for chunk in chunks]

        # Get embeddings
        embeddings = self.embed_batch(texts)

        if len(embeddings) != len(chunks):
            logger.warning(
                f"Embedding count mismatch: got {len(embeddings)}, "
                f"expected {len(chunks)}"
            )

        # Add embeddings to chunks
        for i, chunk in enumerate(chunks):
            if i < len(embeddings):
                chunk["embedding"] = embeddings[i]
            else:
                logger.warning(f"No embedding for chunk {chunk.get('chunk_id')}")

        logger.info(f"Successfully embedded {len(chunks)} chunks")
        return chunks
