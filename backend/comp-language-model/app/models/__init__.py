"""Component 4 (Language Model) SQLAlchemy models.

Importing this package registers the component's tables on the shared
``Base.metadata`` so Alembic autogenerate (``backend/migrations/env.py``)
can see them.
"""

from app.models.chat_history import LlmChatMessage, LlmChatSession

__all__ = ["LlmChatMessage", "LlmChatSession"]
