from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.cattle import AnimalSex
from app.models.marketplace import (ContactPreference, InquiryStatus,
    ListingReportReason, ListingReportStatus, ListingStatus,
    ModerationActionType)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def clean(value):
    if value is None: return None
    return " ".join(value.split())


def validate_currency(value: str):
    value=value.upper()
    if len(value)!=3 or not value.isalpha(): raise ValueError("Currency must be a three-letter code")
    return value


class ListingCreate(StrictRequest):
    cattle_id: UUID
    title: str = Field(min_length=3,max_length=160)
    description: str = Field(min_length=20,max_length=5000)
    asking_price: Decimal = Field(gt=0,max_digits=16,decimal_places=2)
    currency: str = "PKR"
    location: str = Field(min_length=2,max_length=255)
    contact_preference: ContactPreference = ContactPreference.IN_APP
    _text=field_validator("title","description","location")(clean)
    _currency=field_validator("currency")(validate_currency)


class ListingUpdate(StrictRequest):
    title: str|None=Field(default=None,min_length=3,max_length=160)
    description: str|None=Field(default=None,min_length=20,max_length=5000)
    asking_price: Decimal|None=Field(default=None,gt=0,max_digits=16,decimal_places=2)
    currency: str|None=None
    location: str|None=Field(default=None,min_length=2,max_length=255)
    contact_preference: ContactPreference|None=None
    _text=field_validator("title","description","location")(clean)
    @field_validator("currency")
    @classmethod
    def valid_currency(cls,value): return validate_currency(value) if value else value
    @model_validator(mode="after")
    def not_empty(self):
        if not self.model_fields_set: raise ValueError("At least one field is required")
        return self


class PhotoResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; content_type: str; size_bytes: int; is_primary: bool; display_order: int; uploaded_at: datetime


class PublicListingResponse(BaseModel):
    id: UUID; title: str; description: str; asking_price: Decimal; currency: str
    location: str; contact_preference: ContactPreference; status: ListingStatus
    breed_name: str|None; sex: AnimalSex; date_of_birth: date|None
    age_months: int|None; weight_kg: Decimal|None; published_at: datetime|None
    updated_at: datetime; photos: list[PhotoResponse]; saved: bool=False


class SellerListingResponse(PublicListingResponse):
    farm_id: UUID; cattle_id: UUID; seller_user_id: UUID; is_suspended: bool
    suspension_reason: str|None; created_at: datetime


class ListingPage(BaseModel):
    items: list[PublicListingResponse]; total: int; limit: int; offset: int


class StatusChange(StrictRequest):
    reason: str|None=Field(default=None,max_length=500)
    _clean=field_validator("reason")(clean)


class InquiryCreate(StrictRequest):
    message: str=Field(min_length=5,max_length=2000)
    _clean=field_validator("message")(clean)


class InquiryMessageCreate(StrictRequest):
    body: str=Field(min_length=1,max_length=2000)
    _clean=field_validator("body")(clean)


class InquiryMessageResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; sender_user_id: UUID; body: str; created_at: datetime


class InquiryResponse(BaseModel):
    id: UUID; listing_id: UUID; listing_title: str; buyer_user_id: UUID
    buyer_name: str|None=None; status: InquiryStatus; unread: bool
    created_at: datetime; updated_at: datetime; messages: list[InquiryMessageResponse]=[]


class ReportCreate(StrictRequest):
    reason: ListingReportReason
    details: str=Field(min_length=10,max_length=1000)
    _clean=field_validator("details")(clean)


class ReportResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; listing_id: UUID; reason: ListingReportReason; details: str
    status: ListingReportStatus; created_at: datetime


class ModerationCreate(StrictRequest):
    action: ModerationActionType
    reason: str=Field(min_length=5,max_length=1000)
    report_id: UUID|None=None
    _clean=field_validator("reason")(clean)


class SaleConfirm(StrictRequest):
    client_request_id: UUID
    agreed_price: Decimal=Field(gt=0,max_digits=16,decimal_places=2)
    currency: str="PKR"
    sale_date: date
    buyer_reference: str=Field(min_length=2,max_length=200)
    notes: str|None=Field(default=None,max_length=5000)
    _currency=field_validator("currency")(validate_currency)
    _clean=field_validator("buyer_reference","notes")(clean)


class SaleResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; listing_id: UUID; farm_id: UUID; client_request_id: UUID
    agreed_price: Decimal; currency: str; sale_date: date; buyer_reference: str
    financial_transaction_id: UUID; confirmed_by_id: UUID; created_at: datetime


class SellerMetrics(BaseModel):
    active_listings: int; draft_listings: int; archived_listings: int
    sold_listings: int; inquiry_count: int; sale_count: int
    conversion_rate: Decimal; sales_total: Decimal; currency: str


class NotificationResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; event_type: str; listing_id: UUID|None; inquiry_id: UUID|None
    message: str; read_at: datetime|None; created_at: datetime
