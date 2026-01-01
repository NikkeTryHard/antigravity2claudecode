"""Initial debug tables for request/response logging.

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create requests table
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("path", sa.String(length=256), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("agent_type", sa.String(length=64), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("is_streaming", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("request_headers", sa.JSON(), nullable=True),
        sa.Column("request_body", sa.JSON(), nullable=True),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for requests table
    op.create_index("ix_requests_request_id", "requests", ["request_id"], unique=True)
    op.create_index("ix_requests_created_at", "requests", ["created_at"])
    op.create_index("ix_requests_provider", "requests", ["provider"])
    op.create_index("ix_requests_status_code", "requests", ["status_code"])

    # Create sse_events table
    op.create_table(
        "sse_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column("delta_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["requests.request_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for sse_events table
    op.create_index("ix_sse_events_request_id", "sse_events", ["request_id"])
    op.create_index(
        "ix_sse_events_request_sequence",
        "sse_events",
        ["request_id", "sequence"],
    )

    # Create metrics_hourly table
    op.create_table(
        "metrics_hourly",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hour", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hour", "provider", name="uq_metrics_hour_provider"),
    )

    # Create indexes for metrics_hourly table
    op.create_index("ix_metrics_hourly_hour", "metrics_hourly", ["hour"])
    op.create_index("ix_metrics_hourly_provider", "metrics_hourly", ["provider"])


def downgrade() -> None:
    # Drop metrics_hourly table
    op.drop_index("ix_metrics_hourly_provider", table_name="metrics_hourly")
    op.drop_index("ix_metrics_hourly_hour", table_name="metrics_hourly")
    op.drop_table("metrics_hourly")

    # Drop sse_events table
    op.drop_index("ix_sse_events_request_sequence", table_name="sse_events")
    op.drop_index("ix_sse_events_request_id", table_name="sse_events")
    op.drop_table("sse_events")

    # Drop requests table
    op.drop_index("ix_requests_status_code", table_name="requests")
    op.drop_index("ix_requests_provider", table_name="requests")
    op.drop_index("ix_requests_created_at", table_name="requests")
    op.drop_index("ix_requests_request_id", table_name="requests")
    op.drop_table("requests")
