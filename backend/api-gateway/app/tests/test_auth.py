"""Smoke tests for gateway-mounted shared auth routes."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_auth_login_rejects_bad_credentials(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_auth_auditor_login(auth_client: TestClient) -> None:
    resp = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "Auditor", "password": "auditor@123"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "auditor"
    assert body["full_name"] == "Auditor"


def test_auth_signup_and_login(auth_client: TestClient) -> None:
    signup = auth_client.post(
        "/api/v1/auth/signup",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "mobile_number": "+94771234567",
            "country": "Sri Lanka",
            "date_of_birth": "1990-01-15",
            "gender": "female",
            "address": "1 Main St",
            "city": "Colombo",
            "postal_code": "00100",
            "password": "secret1",
            "confirm_password": "secret1",
        },
    )
    assert signup.status_code == 201, signup.text
    login = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "ada@example.com", "password": "secret1"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["role"] == "taxpayer"
    assert body["profile_id"] is None
    assert body["user_id"]
