"""Account create + authenticate against the shared ``users`` table."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.shared.auth.models import User
from backend.shared.utils.logging import logger

# Hardcoded auditor for the admin tool (prototype-only).
AUDITOR_USERNAME = "Auditor"
AUDITOR_PASSWORD = "auditor@123"
# Stable synthetic identity so auditor-owned rows (e.g. llm_chat_sessions, which
# FK to users.id) survive restarts and resolve to the same account every login.
AUDITOR_USER_ID = UUID("00000000-0000-0000-0000-00000000a0d1")
AUDITOR_EMAIL = "auditor@system.local"


def ensure_auditor_user(db: Session) -> UUID | None:
    """Guarantee a ``users`` row for the prototype auditor and return its id.

    Features that persist per-user data through a ``users.id`` foreign key
    (the LLM chat history is the first) need the auditor to exist as a real
    account. Returns ``None`` if the row cannot be created (e.g. read-only DB),
    in which case the caller should fall back to a session with no ``user_id``.
    """
    try:
        existing = db.get(User, AUDITOR_USER_ID)
        if existing is not None:
            return existing.id
        by_email = db.execute(
            select(User).where(User.email == AUDITOR_EMAIL)
        ).scalar_one_or_none()
        if by_email is not None:
            return by_email.id
        db.add(
            User(
                id=AUDITOR_USER_ID,
                email=AUDITOR_EMAIL,
                full_name=AUDITOR_USERNAME,
                password=AUDITOR_PASSWORD,
            )
        )
        db.commit()
        return AUDITOR_USER_ID
    except Exception as exc:  # pragma: no cover - depends on DB perms
        db.rollback()
        logger.warning("Could not ensure auditor users row: {}", exc)
        return None


class InvalidCredentialsError(LookupError):
    """Raised when a username/password pair doesn't match a user record."""


class AmbiguousLoginError(LookupError):
    """Raised when multiple user rows match the same login identifier."""


class EmailTakenError(ValueError):
    """Raised at signup when the email is already registered."""


def create_account(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    mobile_number: str,
    country: str,
    date_of_birth: date,
    gender: str,
    address: str,
    city: str,
    postal_code: str,
    profile_picture: str | None = None,
) -> User:
    """Create a taxpayer account (personal/contact details only)."""
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise EmailTakenError(f"'{email}' is already registered")

    user = User(
        email=email,
        full_name=f"{first_name} {last_name}".strip(),
        first_name=first_name,
        last_name=last_name,
        password=password,
        mobile_number=mobile_number,
        country=country,
        date_of_birth=date_of_birth,
        gender=gender,
        address=address,
        city=city,
        postal_code=postal_code,
        profile_picture=profile_picture,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _latest_profile_id(db: Session, user_id: UUID) -> UUID | None:
    """Resolve Comp 3 financial profile without importing Comp 3 ORM."""
    row = db.execute(
        text(
            """
            SELECT id
            FROM financial_profiles
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"user_id": str(user_id)},
    ).first()
    if row is None:
        return None
    return UUID(str(row[0]))


def authenticate_user(db: Session, username: str, password: str) -> tuple[User, UUID | None]:
    """Verify credentials; return user and optional latest ``financial_profiles.id``.

    Login identifier resolution (shared Azure DB, no local SQLite users):
    1. If ``username`` contains ``@``, match **email only** (exact, case-sensitive).
    2. Otherwise try email exact match first, then ``full_name`` exact match.
    3. When several rows share the same display name, pick the one with a linked
       financial profile; if still tied, the most recently created account.
    """
    login = username.strip()
    if not login or not password:
        raise InvalidCredentialsError("Invalid username or password")

    if "@" in login:
        candidates = list(
            db.execute(select(User).where(User.email == login).order_by(User.created_at.desc()))
            .scalars()
            .all()
        )
    else:
        by_email = list(
            db.execute(select(User).where(User.email == login).order_by(User.created_at.desc()))
            .scalars()
            .all()
        )
        by_name = list(
            db.execute(select(User).where(User.full_name == login).order_by(User.created_at.desc()))
            .scalars()
            .all()
        )
        candidates = by_email if by_email else by_name

    matching = [user for user in candidates if user.password == password]
    if not matching:
        raise InvalidCredentialsError("Invalid username or password")

    def _sort_key(user: User) -> tuple[int, float]:
        profile_id = _latest_profile_id(db, user.id)
        created = user.created_at.timestamp() if user.created_at else 0.0
        return (1 if profile_id is not None else 0, created)

    matching.sort(key=_sort_key, reverse=True)
    user = matching[0]

    # Same password on duplicate full_name rows without email login — ask for email.
    if "@" not in login and len(matching) > 1:
        top = matching[0]
        for other in matching[1:]:
            if other.full_name == top.full_name and other.id != top.id:
                raise AmbiguousLoginError(
                    "Multiple accounts share this username. Sign in with your email address instead."
                )

    profile_id = _latest_profile_id(db, user.id)
    return user, profile_id
