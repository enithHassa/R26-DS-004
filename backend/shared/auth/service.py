"""Account create + authenticate against the shared ``users`` table."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.shared.auth.models import User

# Hardcoded auditor for the admin tool (prototype-only).
AUDITOR_USERNAME = "Auditor"
AUDITOR_PASSWORD = "auditor@123"


class InvalidCredentialsError(LookupError):
    """Raised when a username/password pair doesn't match a user record."""


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
    """Verify credentials; return user and optional latest ``financial_profiles.id``."""
    candidates = list(
        db.execute(
            select(User)
            .where((User.email == username) | (User.full_name == username))
            .order_by(User.created_at.desc())
        )
        .scalars()
        .all()
    )
    matching = [user for user in candidates if user.password == password]
    if not matching:
        raise InvalidCredentialsError("Invalid username or password")

    for user in matching:
        profile_id = _latest_profile_id(db, user.id)
        if profile_id is not None:
            return user, profile_id

    return matching[0], None
