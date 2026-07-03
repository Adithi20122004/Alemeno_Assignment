"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_status_enum = postgresql.ENUM(
        "PENDING", "PROCESSING", "COMPLETED", "FAILED", name="job_status", create_type=False
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column(
            "status",
            job_status_enum,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("row_count_raw", sa.Integer(), nullable=True),
        sa.Column("row_count_clean", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_jobs_id", "jobs", ["id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("txn_id", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("merchant", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("anomaly_reason", sa.String(length=255), nullable=True),
        sa.Column("llm_category", sa.String(length=64), nullable=True),
        sa.Column("llm_failed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_transactions_id", "transactions", ["id"])
    op.create_index("ix_transactions_job_id", "transactions", ["job_id"])
    op.create_index("ix_transactions_txn_id", "transactions", ["txn_id"])
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_txn_job_account", "transactions", ["job_id", "account_id"])

    op.create_table(
        "job_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total_spend_inr", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_spend_usd", sa.Numeric(18, 2), nullable=True),
        sa.Column("top_merchants", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
    )
    op.create_index("ix_job_summaries_id", "job_summaries", ["id"])


def downgrade() -> None:
    op.drop_index("ix_job_summaries_id", table_name="job_summaries")
    op.drop_table("job_summaries")

    op.drop_index("ix_txn_job_account", table_name="transactions")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_index("ix_transactions_txn_id", table_name="transactions")
    op.drop_index("ix_transactions_job_id", table_name="transactions")
    op.drop_index("ix_transactions_id", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_jobs_id", table_name="jobs")
    op.drop_table("jobs")

    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
