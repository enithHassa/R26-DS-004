"""SQLAlchemy ORM models specific to the transaction-semantic component.

These tables hold training labels, taxability decisions, and the human
review queue for the semantic-reasoning pipeline. Other components do not
write here; they consume taxability decisions via the component's API.

This package is loaded by ``backend/migrations/env.py`` via
``importlib.util.spec_from_file_location`` because the parent directory
name (``comp-transaction-sementic``) contains hyphens and therefore
cannot be a regular Python package.
"""

from . import enums  # noqa: F401
from . import review_queue  # noqa: F401
from . import taxability_output  # noqa: F401
from . import transaction_label  # noqa: F401
