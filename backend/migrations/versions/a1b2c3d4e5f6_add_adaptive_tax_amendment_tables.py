"""add adaptive tax amendment pipeline tables

Revision ID: a1b2c3d4e5f6
Revises: 7109b7d4c2a8
Create Date: 2026-08-02 13:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7109b7d4c2a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    amendment_job_status = postgresql.ENUM(
        "uploaded",
        "extracting",
        "extracted",
        "approved",
        "rejected",
        "failed",
        name="amendment_job_status",
        create_type=False,
    )
    amendment_extract_run_status = postgresql.ENUM(
        "started",
        "completed",
        "failed",
        name="amendment_extract_run_status",
        create_type=False,
    )
    rule_source_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        name="rule_source_status",
        create_type=False,
    )
    adaptive_tax_rule_type = postgresql.ENUM(
        "deduction",
        "exemption",
        "rate",
        "definition",
        "limit",
        "condition",
        name="adaptive_tax_rule_type",
        create_type=False,
    )

    amendment_job_status.create(op.get_bind(), checkfirst=True)
    amendment_extract_run_status.create(op.get_bind(), checkfirst=True)
    rule_source_status.create(op.get_bind(), checkfirst=True)
    adaptive_tax_rule_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "amendment_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "status",
            amendment_job_status,
            server_default="uploaded",
            nullable=False,
        ),
        sa.Column(
            "extracted_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_amendment_jobs_file_hash"),
        "amendment_jobs",
        ["file_hash"],
        unique=False,
    )

    op.create_table(
        "amendment_extract_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("amendment_job_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            amendment_extract_run_status,
            server_default="started",
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["amendment_job_id"],
            ["amendment_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_amendment_extract_runs_amendment_job_id"),
        "amendment_extract_runs",
        ["amendment_job_id"],
        unique=False,
    )

    op.create_table(
        "rule_source",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("amendment_job_id", sa.UUID(), nullable=False),
        sa.Column("extract_run_id", sa.UUID(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("section", sa.String(length=64), nullable=False),
        sa.Column("paragraph", sa.String(length=64), nullable=True),
        sa.Column("rule_type", adaptive_tax_rule_type, nullable=False),
        sa.Column("concept_id", sa.String(length=128), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("maximum", sa.Float(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("amends_section", sa.String(length=64), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column(
            "status",
            rule_source_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["amendment_job_id"],
            ["amendment_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["extract_run_id"],
            ["amendment_extract_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rule_source_amendment_job_id"),
        "rule_source",
        ["amendment_job_id"],
        unique=False,
    )

    op.create_table(
        "rule_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_source_id", sa.UUID(), nullable=False),
        sa.Column("amendment_job_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["amendment_job_id"],
            ["amendment_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rule_source_id"],
            ["rule_source.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rule_versions_rule_source_id"),
        "rule_versions",
        ["rule_source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_versions_amendment_job_id"),
        "rule_versions",
        ["amendment_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rule_versions_amendment_job_id"), table_name="rule_versions")
    op.drop_index(op.f("ix_rule_versions_rule_source_id"), table_name="rule_versions")
    op.drop_table("rule_versions")

    op.drop_index(op.f("ix_rule_source_amendment_job_id"), table_name="rule_source")
    op.drop_table("rule_source")

    op.drop_index(
        op.f("ix_amendment_extract_runs_amendment_job_id"),
        table_name="amendment_extract_runs",
    )
    op.drop_table("amendment_extract_runs")

    op.drop_index(op.f("ix_amendment_jobs_file_hash"), table_name="amendment_jobs")
    op.drop_table("amendment_jobs")

    op.execute("DROP TYPE IF EXISTS adaptive_tax_rule_type")
    op.execute("DROP TYPE IF EXISTS rule_source_status")
    op.execute("DROP TYPE IF EXISTS amendment_extract_run_status")
    op.execute("DROP TYPE IF EXISTS amendment_job_status")
