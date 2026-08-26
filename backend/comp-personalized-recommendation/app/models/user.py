"""Canonical user ownership row — re-exported from shared auth.

Kept under Comp 3's ``app.models`` so existing imports and FK metadata
continue to resolve; the table definition lives in ``backend.shared.auth``.
"""

from backend.shared.auth.models import User

__all__ = ["User"]
