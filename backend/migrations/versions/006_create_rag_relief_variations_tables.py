"""Create tables for year-aware RAG relief extraction.

Revision ID: f6a7b8c9d0e1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-24 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = "f6a7b8c9d0e1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

def upgrade():
    """Create new tables for relief variations and tax slabs."""

    # Table 1: Relief Variations (Year-specific)
    op.create_table(
        'rag_relief_variations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relief_name', sa.String(255), nullable=False),
        sa.Column('assessment_year', sa.String(20), nullable=False),

        # Amount & Currency
        sa.Column('cap_amount', sa.String(50), nullable=True),
        sa.Column('cap_currency', sa.String(10), nullable=True),
        sa.Column('is_unlimited', sa.Boolean(), default=False),

        # Dates
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),

        # Act Reference
        sa.Column('source_act', sa.String(255), nullable=False),
        sa.Column('section_ref', sa.String(255), nullable=True),

        # Explanation
        sa.Column('law_quote', sa.Text(), nullable=True),
        sa.Column('how_to_calculate', sa.Text(), nullable=True),
        sa.Column('example_calculation', sa.Text(), nullable=True),

        # Conditions
        sa.Column('eligibility_conditions', postgresql.JSON(), default=[]),
        sa.Column('special_conditions', sa.Text(), nullable=True),

        # Year-to-year change tracking
        sa.Column('previous_year_amount', sa.String(50), nullable=True),
        sa.Column('is_new_relief', sa.Boolean(), default=False),
        sa.Column('is_updated_relief', sa.Boolean(), default=False),
        sa.Column('is_removed_relief', sa.Boolean(), default=False),
        sa.Column('change_description', sa.Text(), nullable=True),

        # Confidence & Status
        sa.Column('confidence_overall', sa.Float(), default=0.0),
        sa.Column('confidence_amount', sa.Float(), default=0.0),
        sa.Column('confidence_explanation', sa.Float(), default=0.0),
        sa.Column('status', sa.String(20), default='pending'),

        # Audit
        sa.Column('extracted_by', sa.String(255), nullable=True),
        sa.Column('approved_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),

        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_relief_year', 'rag_relief_variations', ['relief_name', 'assessment_year'])
    op.create_index('idx_year', 'rag_relief_variations', ['assessment_year'])
    op.create_index('idx_status', 'rag_relief_variations', ['status'])

    # Table 2: Tax Slabs (Year-specific)
    op.create_table(
        'rag_tax_slabs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assessment_year', sa.String(20), nullable=False),

        # Bracket
        sa.Column('income_from', sa.Numeric(15, 2), nullable=False),
        sa.Column('income_to', sa.Numeric(15, 2), nullable=False),
        sa.Column('tax_rate', sa.Float(), nullable=False),
        sa.Column('tax_amount', sa.Numeric(15, 2), nullable=True),

        # Conditions
        sa.Column('applicable_to', postgresql.JSON(), default=[]),
        sa.Column('special_conditions', sa.Text(), nullable=True),

        # Act Reference
        sa.Column('source_act', sa.String(255), nullable=False),
        sa.Column('section_ref', sa.String(255), nullable=True),

        # Explanation
        sa.Column('law_quote', sa.Text(), nullable=True),
        sa.Column('how_calculated', sa.Text(), nullable=True),
        sa.Column('example_calculation', sa.Text(), nullable=True),

        # Year-to-year change
        sa.Column('previous_year_rate', sa.Float(), nullable=True),
        sa.Column('change_description', sa.Text(), nullable=True),

        # Confidence & Status
        sa.Column('confidence_overall', sa.Float(), default=0.0),
        sa.Column('status', sa.String(20), default='pending'),

        # Audit
        sa.Column('extracted_by', sa.String(255), nullable=True),
        sa.Column('approved_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),

        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_slab_year', 'rag_tax_slabs', ['assessment_year'])
    op.create_index('idx_slab_bracket', 'rag_tax_slabs', ['assessment_year', 'income_from', 'income_to'])

    # Table 3: Extraction History (Track what was extracted from which act)
    op.create_table(
        'rag_extraction_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_act', sa.String(255), nullable=False),
        sa.Column('upload_date', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('pdf_filename', sa.String(255), nullable=True),
        sa.Column('total_chunks', sa.Integer(), nullable=False),
        sa.Column('reliefs_extracted', sa.Integer(), default=0),
        sa.Column('tax_slabs_extracted', sa.Integer(), default=0),
        sa.Column('extraction_status', sa.String(20), default='pending'),
        sa.Column('extracted_by', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_extraction_history_status', 'rag_extraction_history', ['extraction_status'])
    op.create_index('idx_extraction_history_act', 'rag_extraction_history', ['source_act'])


def downgrade():
    """Drop the tables if rolling back."""
    op.drop_table('rag_extraction_history')
    op.drop_table('rag_tax_slabs')
    op.drop_table('rag_relief_variations')
