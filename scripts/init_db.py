"""
Database initialization script.

Creates the tax_advisory database on Azure PostgreSQL if it doesn't exist,
then verifies the connection through SQLAlchemy.

Usage:
    python -m scripts.init_db
"""

import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.shared.config.settings import settings


def create_database_if_not_exists() -> None:
    """Connect to the default 'postgres' database and create tax_advisory."""
    conn = psycopg2.connect(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        dbname="postgres",
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        sslmode=settings.DATABASE_SSLMODE,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (settings.DATABASE_NAME,)
    )
    exists = cursor.fetchone()

    if exists:
        print(f"Database '{settings.DATABASE_NAME}' already exists.")
    else:
        cursor.execute(f'CREATE DATABASE "{settings.DATABASE_NAME}"')
        print(f"Database '{settings.DATABASE_NAME}' created successfully.")

    cursor.close()
    conn.close()


def verify_connection() -> None:
    """Verify SQLAlchemy can connect to the target database."""
    from backend.shared.config.database import engine

    with engine.connect() as conn:
        result = conn.execute(
            __import__("sqlalchemy").text("SELECT version()")
        )
        version = result.scalar()
        print("Connected successfully!")
        print(f"  Host:     {settings.DATABASE_HOST}")
        print(f"  Database: {settings.DATABASE_NAME}")
        print(f"  Postgres: {version}")


if __name__ == "__main__":
    print("=" * 60)
    print("  Tax Advisory System - Database Initialization")
    print("=" * 60)
    print()

    print("[1/2] Creating database if not exists...")
    try:
        create_database_if_not_exists()
    except Exception as e:
        print(f"  ERROR: {e}")
        print("  Make sure your Azure server is started and .env is configured.")
        sys.exit(1)

    print()
    print("[2/2] Verifying SQLAlchemy connection...")
    try:
        verify_connection()
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print()
    print("Database setup complete. You can now run migrations with:")
    print("  alembic upgrade head")
