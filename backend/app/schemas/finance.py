from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.finance import (AssetCondition, AssetStatus, BudgetPeriod,
    CattleTransactionType, FinanceCategoryType, FinanceTransactionStatus,
    PaymentMethod)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def clean(value):
    if value is None: return None
    return " ".join(value.split()) or None


def validate_currency(value: str) -> str:
    value = value.upper()
    if len(value) != 3 or not value.isalpha(): raise ValueError("Currency must be a three-letter code")
    return value


class CategoryCreate(StrictRequest):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)
    category_type: FinanceCategoryType
    _clean = field_validator("code", "name")(clean)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; farm_id: UUID; code: str; name: str; category_type: FinanceCategoryType
    is_system: bool; is_active: bool; created_by_id: UUID; created_at: datetime


class TransactionCreate(StrictRequest):
    client_request_id: UUID
    category_id: UUID
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    currency: str = "PKR"
    business_date: date
    due_date: date | None = None
    counterparty: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=150)
    description: str = Field(min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    cattle_id: UUID | None = None
    post_now: bool = False
    _currency = field_validator("currency")(validate_currency)
    _clean = field_validator("counterparty", "reference", "description", "notes")(clean)

    @model_validator(mode="after")
    def dates(self):
        if self.due_date and self.due_date < self.business_date: raise ValueError("due_date cannot precede business_date")
        return self


class TransactionUpdate(StrictRequest):
    category_id: UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=16, decimal_places=2)
    business_date: date | None = None; due_date: date | None = None
    counterparty: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    _clean = field_validator("counterparty", "reference", "description", "notes")(clean)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set: raise ValueError("At least one field is required")
        return self


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; farm_id: UUID; client_request_id: UUID; transaction_type: FinanceCategoryType
    category_id: UUID; amount: Decimal; adjusted_amount: Decimal; paid_amount: Decimal; outstanding_amount: Decimal
    payment_status: str; currency: str; business_date: date; due_date: date | None
    status: FinanceTransactionStatus; counterparty: str | None; reference: str | None
    description: str; notes: str | None; cattle_id: UUID | None; source_type: str; source_id: UUID
    created_by_id: UUID; posted_by_id: UUID | None; posted_at: datetime | None; created_at: datetime; updated_at: datetime


class AdjustmentCreate(StrictRequest):
    client_request_id: UUID
    amount_delta: Decimal = Field(max_digits=16, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)
    _clean = field_validator("reason")(clean)
    @field_validator("amount_delta")
    @classmethod
    def nonzero(cls, value):
        if value == 0: raise ValueError("Adjustment must be non-zero")
        return value


class PaymentCreate(StrictRequest):
    client_request_id: UUID; transaction_id: UUID
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    currency: str = "PKR"; paid_at: datetime; method: PaymentMethod
    reference: str | None = Field(default=None, max_length=150); notes: str | None = Field(default=None, max_length=5000)
    _currency = field_validator("currency")(validate_currency)
    _clean = field_validator("reference", "notes")(clean)
    @field_validator("paid_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None: raise ValueError("paid_at must include a timezone")
        return value


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; farm_id: UUID; transaction_id: UUID; client_request_id: UUID; amount: Decimal
    currency: str; paid_at: datetime; method: PaymentMethod; reference: str | None; notes: str | None
    recorded_by_id: UUID; created_at: datetime


class MilkSaleCreate(StrictRequest):
    client_request_id: UUID; sale_date: date
    quantity_liters: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    price_per_liter: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: str = "PKR"; customer: str = Field(min_length=2, max_length=200)
    invoice_number: str = Field(min_length=1, max_length=100); notes: str | None = Field(default=None, max_length=5000)
    _currency = field_validator("currency")(validate_currency)
    _clean = field_validator("customer", "invoice_number", "notes")(clean)


class CattleTransactionCreate(StrictRequest):
    client_request_id: UUID; cattle_id: UUID; transaction_type: CattleTransactionType
    transaction_date: date; amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    currency: str = "PKR"; counterparty: str = Field(min_length=2, max_length=200)
    reference: str | None = Field(default=None, max_length=150); notes: str | None = Field(default=None, max_length=5000)
    _currency = field_validator("currency")(validate_currency)
    _clean = field_validator("counterparty", "reference", "notes")(clean)


class BudgetCreate(StrictRequest):
    period: BudgetPeriod; period_start: date; category_id: UUID
    amount: Decimal = Field(ge=0, max_digits=16, decimal_places=2); currency: str = "PKR"
    notes: str | None = Field(default=None, max_length=5000)
    _currency = field_validator("currency")(validate_currency)


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; farm_id: UUID; period: BudgetPeriod; period_start: date; category_id: UUID
    amount: Decimal; currency: str; notes: str | None; created_by_id: UUID; created_at: datetime


class BudgetComparisonResponse(BaseModel):
    budget_id: UUID; category_id: UUID; period: BudgetPeriod
    period_start: date; period_end: date; budgeted: Decimal; actual: Decimal
    remaining: Decimal; over_budget: bool; currency: str


class CustomerBalanceResponse(BaseModel):
    customer: str; currency: str; invoice_count: int
    sales_total: Decimal; paid_total: Decimal; outstanding_balance: Decimal
    last_sale_date: date


class AssetCreate(StrictRequest):
    asset_code: str = Field(min_length=1, max_length=80); name: str = Field(min_length=2, max_length=200)
    category: str = Field(min_length=2, max_length=100); purchase_date: date | None = None
    purchase_value: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    currency: str | None = None; supplier: str | None = Field(default=None, max_length=200)
    condition: AssetCondition; location: str | None = Field(default=None, max_length=200)
    assigned_to: str | None = Field(default=None, max_length=200); depreciation_method: str | None = Field(default=None, max_length=50)
    useful_life_years: int | None = Field(default=None, ge=1, le=100); notes: str | None = Field(default=None, max_length=5000)
    @field_validator("currency")
    @classmethod
    def optional_currency(cls, value): return validate_currency(value) if value else value
    @model_validator(mode="after")
    def purchase_pair(self):
        if (self.purchase_value is None) != (self.currency is None): raise ValueError("purchase_value and currency must be provided together")
        return self


class AssetUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=2, max_length=200); category: str | None = Field(default=None, min_length=2, max_length=100)
    condition: AssetCondition | None = None; status: AssetStatus | None = None
    location: str | None = Field(default=None, max_length=200); assigned_to: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; farm_id: UUID; asset_code: str; name: str; category: str; purchase_date: date | None
    purchase_value: Decimal | None; currency: str | None; supplier: str | None; condition: AssetCondition
    status: AssetStatus; location: str | None; assigned_to: str | None; depreciation_method: str | None
    useful_life_years: int | None; notes: str | None; created_by_id: UUID; created_at: datetime


class MaintenanceCreate(StrictRequest):
    client_request_id: UUID; performed_on: date; description: str = Field(min_length=2, max_length=500)
    vendor: str | None = Field(default=None, max_length=200); cost: Decimal = Field(ge=0, max_digits=16, decimal_places=2)
    currency: str = "PKR"; next_due_date: date | None = None; post_expense: bool = True
    notes: str | None = Field(default=None, max_length=5000)
    _currency = field_validator("currency")(validate_currency)
