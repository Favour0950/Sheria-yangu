"""
src/db/models.py — SQLAlchemy models matching docs/erd-and-security.md exactly.

Six tables, one deliberate asymmetry: `identity` holds phone_hash/email/token,
and everything else (`responses`, `memoranda`, `notification_log`) references
identity only via the random, non-derived `token` column — never phone_hash,
never email. See docs/erd-and-security.md for the full write-up on why.

This targets a LOCAL Postgres instance now (see docs/postgres-setup.md) and is
meant to be pointed at the KamiLimu-provisioned DigitalOcean droplet Postgres
later by changing only DATABASE_URL in .env — the schema itself doesn't change.

Usage:
  from db.models import Base, Identity, Bill, Clause, Response, Memorandum, NotificationLog
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Identity(Base):
    """
    The one table allowed to hold phone_hash/email. Never joined against by
    analytics or notification-sending code paths except the single audited
    job that writes notification_log.identity_joined = true.
    """
    __tablename__ = "identity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False,
                                             doc="HMAC-SHA256 of phone number, keyed with a server-side pepper stored outside the DB")
    email_encrypted: Mapped[str | None] = mapped_column(String, nullable=True,
                                                          doc="present only if the user opts into email; encrypted at rest, not hashed, because it must be sendable")
    notify_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    constituency: Mapped[str | None] = mapped_column(String, nullable=True,
                                                       doc="self-reported at registration, not verified against the voter roll")
    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4,
                                              doc="randomly generated, NOT derived from phone_hash/email — the pseudonymous public identifier")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[str] = mapped_column(String, nullable=False, doc="national | county")
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="needs_manual_review",
                                         doc="needs_manual_review | open | closed — dashboards must only render status == 'open'")
    opens_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id"), nullable=True)

    clauses: Mapped[list["Clause"]] = relationship(back_populates="bill", foreign_keys="Clause.bill_id")


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    clause_number: Mapped[str] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_sw: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)

    bill: Mapped["Bill"] = relationship(back_populates="clauses", foreign_keys=[bill_id])


class Response(Base):
    """Never stores phone_hash/email — only the pseudonymous token."""
    __tablename__ = "responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False,
                                              doc="soft reference to identity.token — see erd-and-security.md")
    clause_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=False)
    vote: Mapped[str] = mapped_column(String, nullable=False, doc="kubali | kataa")
    constituency_snapshot: Mapped[str | None] = mapped_column(
        String, nullable=True,
        doc="copied from identity.constituency at vote time — a static snapshot so analytics never re-touches identity")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Memorandum(Base):
    __tablename__ = "memoranda"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_read_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_not_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_terms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft", doc="draft | sent | failed")


class NotificationLog(Base):
    """
    identity_joined is the audit flag: true only on the one run that legitimately
    read the identity table (e.g. to look up a phone number to send an SMS to).
    Every other write to this table should have it false.
    """
    __tablename__ = "notification_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False, doc="inapp | sms | email")
    identity_joined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
