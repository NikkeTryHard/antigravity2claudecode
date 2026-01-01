"""
SQLAlchemy models for debug storage.

Stores request/response data for debugging and replay.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Request(Base):
    """
    Stores API request/response data.

    Captures full request and response for debugging and replay.
    """

    __tablename__ = "requests"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Request metadata
    request_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    method: Mapped[str] = mapped_column(String(10), default="POST")
    path: Mapped[str] = mapped_column(String(255), index=True)

    # Routing info
    provider: Mapped[str] = mapped_column(String(50), index=True)
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    matched_rule: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Response info
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_streaming: Mapped[bool] = mapped_column(default=False)

    # Token usage
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error info
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Full request/response (JSON)
    request_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_headers: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    sse_events: Mapped[list["SSEEvent"]] = relationship(
        "SSEEvent",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="SSEEvent.sequence",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_requests_created_desc", created_at.desc()),
        Index("idx_requests_provider_created", provider, created_at.desc()),
        Index("idx_requests_status_created", status_code, created_at.desc()),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "request_id": self.request_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "method": self.method,
            "path": self.path,
            "provider": self.provider,
            "agent_type": self.agent_type,
            "model": self.model,
            "matched_rule": self.matched_rule,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "is_streaming": self.is_streaming,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "error": self.error,
            "error_type": self.error_type,
        }

    def to_full_dict(self) -> dict[str, Any]:
        """Convert to dictionary with full request/response data."""
        data = self.to_dict()
        data.update(
            {
                "request_headers": self.request_headers,
                "request_body": self.request_body,
                "response_headers": self.response_headers,
                "response_body": self.response_body,
                "sse_events_count": len(self.sse_events) if self.sse_events else 0,
            }
        )
        return data


class SSEEvent(Base):
    """
    Stores SSE stream events for streaming requests.

    Allows replay of streaming responses.
    """

    __tablename__ = "sse_events"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to request
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requests.id", ondelete="CASCADE"),
        index=True,
    )

    # Event data
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    delta_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationship
    request: Mapped["Request"] = relationship("Request", back_populates="sse_events")

    # Indexes
    __table_args__ = (Index("idx_sse_request_seq", request_id, sequence),)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "delta_ms": self.delta_ms,
        }


class MetricsHourly(Base):
    """
    Hourly aggregated metrics.

    Pre-aggregated stats for dashboard performance.
    """

    __tablename__ = "metrics_hourly"

    # Primary key (hour bucket)
    hour: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )

    # Request counts
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    total_streaming: Mapped[int] = mapped_column(Integer, default=0)

    # Latency stats
    avg_latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    p50_latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    p95_latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    p99_latency_ms: Mapped[float | None] = mapped_column(nullable=True)

    # Token usage
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Breakdown by provider/agent (JSON)
    by_provider: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    by_agent_type: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    by_model: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hour": self.hour.isoformat(),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "total_streaming": self.total_streaming,
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "by_provider": self.by_provider,
            "by_agent_type": self.by_agent_type,
            "by_model": self.by_model,
        }
