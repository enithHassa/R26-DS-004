"""Shared SQLAlchemy ORM models.

Importing this package registers all *cross-component* tables with
``Base.metadata`` so Alembic's autogenerate can see them. Component-specific
tables live inside their respective ``backend/<component>/db/`` packages and
are loaded separately by ``backend/migrations/env.py``.
"""

from backend.shared.db.enums import TxnDirection, txn_direction_enum
from backend.shared.db.model_run import ModelRun
from backend.shared.db.transaction import Transaction

__all__ = [
    "ModelRun",
    "Transaction",
    "TxnDirection",
    "txn_direction_enum",
]
