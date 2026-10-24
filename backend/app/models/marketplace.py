import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime,
    Enum, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text,
    UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ListingStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    ARCHIVED = "ARCHIVED"


class ContactPreference(str, enum.Enum):
    IN_APP = "IN_APP"
    SHARE_ON_REQUEST = "SHARE_ON_REQUEST"


class InquiryStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ListingReportReason(str, enum.Enum):
    SUSPICIOUS = "SUSPICIOUS"
    MISLEADING = "MISLEADING"
    INAPPROPRIATE_IMAGE = "INAPPROPRIATE_IMAGE"
    OTHER = "OTHER"


class ListingReportStatus(str, enum.Enum):
    OPEN = "OPEN"
    DISMISSED = "DISMISSED"
    ACTIONED = "ACTIONED"


class ModerationActionType(str, enum.Enum):
    SUSPEND = "SUSPEND"
    RESTORE = "RESTORE"
    REMOVE = "REMOVE"
    DISMISS_REPORT = "DISMISS_REPORT"


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_marketplace_listing_cattle_scope"),
        UniqueConstraint("id", "farm_id", name="uq_marketplace_listing_scope"),
        CheckConstraint("asking_price > 0", name="ck_marketplace_listing_price_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_marketplace_listing_currency"),
        Index("uq_marketplace_active_cattle", "cattle_id", unique=True, postgresql_where=text("status IN ('DRAFT','PUBLISHED','RESERVED')")),
        Index("ix_marketplace_browse", "status", "is_suspended", "published_at"),
        Index("ix_marketplace_seller", "farm_id", "status", "updated_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    seller_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    asking_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", server_default="PKR", nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_preference: Mapped[ContactPreference] = mapped_column(Enum(ContactPreference, name="marketplace_contact_preference"), default=ContactPreference.IN_APP, server_default="IN_APP", nullable=False)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus, name="marketplace_listing_status"), default=ListingStatus.DRAFT, server_default="DRAFT", nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    suspension_reason: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MarketplaceListingPhoto(Base):
    __tablename__ = "marketplace_listing_photos"
    __table_args__ = (
        ForeignKeyConstraint(["listing_id", "farm_id"], ["marketplace_listings.id", "marketplace_listings.farm_id"], ondelete="CASCADE", name="fk_marketplace_photo_listing_scope"),
        UniqueConstraint("listing_id", "content_sha256", name="uq_marketplace_photo_content"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_marketplace_photo_size"),
        Index("uq_marketplace_primary_photo", "listing_id", unique=True, postgresql_where=text("is_primary AND removed_at IS NULL")),
        Index("ix_marketplace_photo_active", "listing_id", "display_order", "uploaded_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    display_order: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))


class MarketplaceInquiry(Base):
    __tablename__ = "marketplace_inquiries"
    __table_args__ = (
        ForeignKeyConstraint(["listing_id", "farm_id"], ["marketplace_listings.id", "marketplace_listings.farm_id"], ondelete="RESTRICT", name="fk_marketplace_inquiry_listing_scope"),
        UniqueConstraint("listing_id", "buyer_user_id", name="uq_marketplace_inquiry_buyer_listing"),
        Index("ix_marketplace_inquiry_seller", "farm_id", "status", "updated_at"),
        Index("ix_marketplace_inquiry_buyer", "buyer_user_id", "updated_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    buyer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[InquiryStatus] = mapped_column(Enum(InquiryStatus, name="marketplace_inquiry_status"), default=InquiryStatus.OPEN, server_default="OPEN", nullable=False)
    seller_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyer_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MarketplaceInquiryMessage(Base):
    __tablename__ = "marketplace_inquiry_messages"
    __table_args__ = (Index("ix_marketplace_message_thread", "inquiry_id", "created_at"), CheckConstraint("length(body) BETWEEN 1 AND 2000", name="ck_marketplace_message_length"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inquiry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_inquiries.id", ondelete="CASCADE"), nullable=False)
    sender_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceFavorite(Base):
    __tablename__ = "marketplace_favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id", name="uq_marketplace_favorite_user_listing"), Index("ix_marketplace_favorite_user", "user_id", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceListingStatusHistory(Base):
    __tablename__ = "marketplace_listing_status_history"
    __table_args__ = (Index("ix_marketplace_status_history", "listing_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), nullable=False)
    previous_status: Mapped[ListingStatus | None] = mapped_column(Enum(ListingStatus, name="marketplace_listing_status", create_type=False))
    new_status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus, name="marketplace_listing_status", create_type=False), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceListingReport(Base):
    __tablename__ = "marketplace_listing_reports"
    __table_args__ = (UniqueConstraint("listing_id", "reporter_user_id", name="uq_marketplace_report_user_listing"), Index("ix_marketplace_report_queue", "status", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), nullable=False)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[ListingReportReason] = mapped_column(Enum(ListingReportReason, name="marketplace_report_reason"), nullable=False)
    details: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[ListingReportStatus] = mapped_column(Enum(ListingReportStatus, name="marketplace_report_status"), default=ListingReportStatus.OPEN, server_default="OPEN", nullable=False)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceModerationAction(Base):
    __tablename__ = "marketplace_moderation_actions"
    __table_args__ = (Index("ix_marketplace_moderation_listing", "listing_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), nullable=False)
    report_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listing_reports.id", ondelete="RESTRICT"))
    action: Mapped[ModerationActionType] = mapped_column(Enum(ModerationActionType, name="marketplace_moderation_action"), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceSaleConfirmation(Base):
    __tablename__ = "marketplace_sale_confirmations"
    __table_args__ = (
        UniqueConstraint("listing_id", name="uq_marketplace_sale_listing"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_marketplace_sale_request"),
        ForeignKeyConstraint(["listing_id", "farm_id"], ["marketplace_listings.id", "marketplace_listings.farm_id"], ondelete="RESTRICT", name="fk_marketplace_sale_listing_scope"),
        ForeignKeyConstraint(["financial_transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_marketplace_sale_finance_scope"),
        CheckConstraint("agreed_price > 0", name="ck_marketplace_sale_price_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_marketplace_sale_currency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agreed_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    buyer_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    financial_transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    confirmed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceAuditEvent(Base):
    __tablename__ = "marketplace_audit_events"
    __table_args__ = (Index("ix_marketplace_audit_entity", "farm_id", "entity_type", "entity_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MarketplaceNotification(Base):
    __tablename__ = "marketplace_notifications"
    __table_args__ = (Index("ix_marketplace_notification_user", "user_id", "read_at", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"))
    inquiry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_inquiries.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
