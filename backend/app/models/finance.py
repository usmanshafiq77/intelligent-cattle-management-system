import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FinanceCategoryType(str, enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class FinanceTransactionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"


class FinanceSourceType(str, enum.Enum):
    MANUAL = "MANUAL"
    FEED_PURCHASE = "FEED_PURCHASE"
    MILK_SALE = "MILK_SALE"
    CATTLE_PURCHASE = "CATTLE_PURCHASE"
    CATTLE_SALE = "CATTLE_SALE"
    ASSET_MAINTENANCE = "ASSET_MAINTENANCE"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    MOBILE_WALLET = "MOBILE_WALLET"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class CattleTransactionType(str, enum.Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"


class BudgetPeriod(str, enum.Enum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class AssetCondition(str, enum.Enum):
    NEW = "NEW"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class AssetStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"
    DISPOSED = "DISPOSED"
    SOLD = "SOLD"


class FinanceCategory(Base):
    __tablename__ = "finance_categories"
    __table_args__ = (UniqueConstraint("farm_id", "code", name="uq_finance_category_farm_code"), UniqueConstraint("id", "farm_id", name="uq_finance_category_scope"), Index("ix_finance_category_active", "farm_id", "category_type", "is_active"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_type: Mapped[FinanceCategoryType] = mapped_column(Enum(FinanceCategoryType, name="finance_category_type"), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"
    __table_args__ = (
        ForeignKeyConstraint(["category_id", "farm_id"], ["finance_categories.id", "finance_categories.farm_id"], ondelete="RESTRICT", name="fk_finance_transaction_category_scope"),
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_finance_transaction_cattle_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_finance_transaction_request"),
        UniqueConstraint("farm_id", "source_type", "source_id", name="uq_finance_transaction_source"),
        UniqueConstraint("id", "farm_id", name="uq_finance_transaction_scope"),
        CheckConstraint("amount > 0", name="ck_finance_transaction_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_finance_transaction_currency"),
        CheckConstraint("(status = 'POSTED' AND posted_at IS NOT NULL) OR (status <> 'POSTED')", name="ck_finance_transaction_posted_at"),
        Index("ix_finance_transaction_report", "farm_id", "transaction_type", "business_date", "status"), Index("ix_finance_transaction_counterparty", "farm_id", "counterparty"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_type: Mapped[FinanceCategoryType] = mapped_column(Enum(FinanceCategoryType, name="finance_category_type", create_type=False), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", server_default="PKR", nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[FinanceTransactionStatus] = mapped_column(Enum(FinanceTransactionStatus, name="finance_transaction_status"), default=FinanceTransactionStatus.DRAFT, server_default="DRAFT", nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    cattle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_type: Mapped[FinanceSourceType] = mapped_column(Enum(FinanceSourceType, name="finance_source_type"), default=FinanceSourceType.MANUAL, server_default="MANUAL", nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    posted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FinancialAdjustment(Base):
    __tablename__ = "financial_adjustments"
    __table_args__ = (ForeignKeyConstraint(["transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_finance_adjustment_transaction_scope"), UniqueConstraint("farm_id", "client_request_id", name="uq_finance_adjustment_request"), CheckConstraint("amount_delta <> 0", name="ck_finance_adjustment_nonzero"), Index("ix_finance_adjustment_transaction", "farm_id", "transaction_id", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount_delta: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinancePayment(Base):
    __tablename__ = "finance_payments"
    __table_args__ = (ForeignKeyConstraint(["transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_finance_payment_transaction_scope"), UniqueConstraint("farm_id", "client_request_id", name="uq_finance_payment_request"), CheckConstraint("amount > 0", name="ck_finance_payment_positive"), Index("ix_finance_payment_history", "farm_id", "transaction_id", "paid_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="finance_payment_method"), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MilkSale(Base):
    __tablename__ = "milk_sales"
    __table_args__ = (ForeignKeyConstraint(["transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_milk_sale_transaction_scope"), UniqueConstraint("farm_id", "client_request_id", name="uq_milk_sale_request"), UniqueConstraint("farm_id", "invoice_number", name="uq_milk_sale_invoice"), UniqueConstraint("transaction_id", name="uq_milk_sale_transaction"), CheckConstraint("quantity_liters > 0 AND price_per_liter >= 0 AND total_amount >= 0", name="ck_milk_sale_amounts"), Index("ix_milk_sale_report", "farm_id", "sale_date"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_liters: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    price_per_liter: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    customer: Mapped[str] = mapped_column(String(200), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CattleFinanceTransaction(Base):
    __tablename__ = "cattle_finance_transactions"
    __table_args__ = (ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_cattle_finance_cattle_scope"), ForeignKeyConstraint(["transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_cattle_finance_transaction_scope"), UniqueConstraint("farm_id", "client_request_id", name="uq_cattle_finance_request"), UniqueConstraint("transaction_id", name="uq_cattle_finance_transaction"), Index("ix_cattle_finance_history", "farm_id", "cattle_id", "transaction_date"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_type: Mapped[CattleTransactionType] = mapped_column(Enum(CattleTransactionType, name="cattle_finance_transaction_type"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    counterparty: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinanceBudget(Base):
    __tablename__ = "finance_budgets"
    __table_args__ = (ForeignKeyConstraint(["category_id", "farm_id"], ["finance_categories.id", "finance_categories.farm_id"], ondelete="RESTRICT", name="fk_finance_budget_category_scope"), UniqueConstraint("farm_id", "period", "period_start", "category_id", name="uq_finance_budget_period_category"), CheckConstraint("amount >= 0", name="ck_finance_budget_nonnegative"), Index("ix_finance_budget_period", "farm_id", "period_start"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[BudgetPeriod] = mapped_column(Enum(BudgetPeriod, name="finance_budget_period"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="PKR", server_default="PKR", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FarmAsset(Base):
    __tablename__ = "farm_assets"
    __table_args__ = (UniqueConstraint("farm_id", "asset_code", name="uq_farm_asset_code"), UniqueConstraint("id", "farm_id", name="uq_farm_asset_scope"), CheckConstraint("purchase_value IS NULL OR purchase_value >= 0", name="ck_farm_asset_value_nonnegative"), Index("ix_farm_asset_status", "farm_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    asset_code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    supplier: Mapped[str | None] = mapped_column(String(200))
    condition: Mapped[AssetCondition] = mapped_column(Enum(AssetCondition, name="farm_asset_condition"), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus, name="farm_asset_status"), default=AssetStatus.ACTIVE, server_default="ACTIVE", nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    assigned_to: Mapped[str | None] = mapped_column(String(200))
    depreciation_method: Mapped[str | None] = mapped_column(String(50))
    useful_life_years: Mapped[int | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AssetMaintenance(Base):
    __tablename__ = "asset_maintenance_records"
    __table_args__ = (ForeignKeyConstraint(["asset_id", "farm_id"], ["farm_assets.id", "farm_assets.farm_id"], ondelete="RESTRICT", name="fk_asset_maintenance_asset_scope"), ForeignKeyConstraint(["financial_transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_asset_maintenance_finance_scope"), UniqueConstraint("farm_id", "client_request_id", name="uq_asset_maintenance_request"), CheckConstraint("cost >= 0", name="ck_asset_maintenance_cost_nonnegative"), Index("ix_asset_maintenance_history", "farm_id", "asset_id", "performed_on"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    performed_on: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(200))
    cost: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    next_due_date: Mapped[date | None] = mapped_column(Date)
    financial_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinanceAuditEvent(Base):
    __tablename__ = "finance_audit_events"
    __table_args__ = (Index("ix_finance_audit_entity", "farm_id", "entity_type", "entity_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FinanceAttachment(Base):
    __tablename__ = "finance_attachments"
    __table_args__ = (ForeignKeyConstraint(["transaction_id", "farm_id"], ["financial_transactions.id", "financial_transactions.farm_id"], ondelete="RESTRICT", name="fk_finance_attachment_transaction_scope"), CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_finance_attachment_size"), Index("ix_finance_attachment_active", "farm_id", "transaction_id", "uploaded_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
