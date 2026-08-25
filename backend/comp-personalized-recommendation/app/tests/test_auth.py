"""Login tests for the User View (customer-facing dashboard)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User as UserORM


def test_login_rejects_bad_credentials(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_succeeds_when_duplicate_full_names_exist(
    client: TestClient, db_session: Session
) -> None:
    """Re-seeding can leave several users named Taxpayer_NNNNN.

    ``scalar_one_or_none`` used to 500 here; login must pick a password match.
    """
    name = "Taxpayer_25265"
    password = "25265@Tax"
    db_session.add_all(
        [
            UserORM(email="dup-a@synthetic.local", full_name=name, password=password),
            UserORM(email="dup-b@synthetic.local", full_name=name, password=password),
        ]
    )
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": name, "password": password},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "taxpayer"
    assert body["full_name"] == name
    assert body["user_id"]


def test_login_with_email_for_account_without_profile(
    client: TestClient, db_session: Session
) -> None:
    db_session.add(
        UserORM(
            email="new.user@example.com",
            full_name="New User",
            password="secret1",
        )
    )
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "new.user@example.com", "password": "secret1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "taxpayer"
    assert body["profile_id"] is None
