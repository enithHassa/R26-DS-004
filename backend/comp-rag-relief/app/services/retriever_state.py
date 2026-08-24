"""Shared retriever state across routers."""

from app.services.retriever import ReliefRetriever

# Global retriever instance (shared across all routers)
_retriever_instance: ReliefRetriever | None = None


def set_retriever(retriever: ReliefRetriever) -> None:
    """Set the global retriever instance."""
    global _retriever_instance
    _retriever_instance = retriever


def get_retriever() -> ReliefRetriever | None:
    """Get the global retriever instance."""
    return _retriever_instance


def has_retriever() -> bool:
    """Check if retriever is initialized."""
    return _retriever_instance is not None
