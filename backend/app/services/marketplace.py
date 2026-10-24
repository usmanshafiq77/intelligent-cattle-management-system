import hashlib
import struct
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cattle import (Breed, Cattle, CattleLifecycleEvent, CattleStatus,
    CattleWeightRecord)
from app.models.finance import (CattleFinanceTransaction, CattleTransactionType,
    FinanceCategoryType, FinanceSourceType, FinanceTransactionStatus,
    FinancialTransaction)
from app.models.marketplace import (InquiryStatus, ListingStatus,
    MarketplaceAuditEvent, MarketplaceInquiry, MarketplaceInquiryMessage,
    MarketplaceListing, MarketplaceListingPhoto,
    MarketplaceListingStatusHistory, MarketplaceNotification,
    MarketplaceSaleConfirmation)
from app.models.user import User
from app.services.cattle import latest_lifecycle_event, validate_operational_lifecycle_time
from app.services.finance import ensure_categories


class MarketplaceValidationError(ValueError): pass


def money(value): return Decimal(value).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)


def audit(db: Session, listing: MarketplaceListing, action: str, summary: str, actor_id: UUID):
    db.add(MarketplaceAuditEvent(farm_id=listing.farm_id,entity_type="listing",entity_id=listing.id,action=action,summary=summary,actor_user_id=actor_id))


def notify(db: Session, user_id: UUID, event_type: str, message: str, *, listing_id=None, inquiry_id=None):
    db.add(MarketplaceNotification(user_id=user_id,event_type=event_type,message=message,listing_id=listing_id,inquiry_id=inquiry_id))


def history(db: Session, listing: MarketplaceListing, status: ListingStatus, actor_id: UUID, reason: str|None=None):
    previous=listing.status
    db.add(MarketplaceListingStatusHistory(listing_id=listing.id,previous_status=previous,new_status=status,reason=reason,actor_id=actor_id))
    listing.status=status
    now=datetime.now(timezone.utc)
    if status==ListingStatus.PUBLISHED: listing.published_at=now; listing.archived_at=None
    if status==ListingStatus.ARCHIVED: listing.archived_at=now


def listing_or_error(db: Session, listing_id: UUID, *, farm_id: UUID|None=None, lock=False):
    q=select(MarketplaceListing).where(MarketplaceListing.id==listing_id)
    if farm_id: q=q.where(MarketplaceListing.farm_id==farm_id)
    if lock: q=q.with_for_update()
    row=db.scalar(q)
    if not row: raise MarketplaceValidationError("Marketplace listing not found")
    return row


def photo_rows(db: Session, listing_id: UUID):
    return db.scalars(select(MarketplaceListingPhoto).where(MarketplaceListingPhoto.listing_id==listing_id,MarketplaceListingPhoto.removed_at.is_(None)).order_by(MarketplaceListingPhoto.is_primary.desc(),MarketplaceListingPhoto.display_order,MarketplaceListingPhoto.uploaded_at)).all()


def listing_payload(db: Session, listing: MarketplaceListing, *, user_id: UUID|None=None, seller=False):
    animal=db.get(Cattle,listing.cattle_id); breed=db.get(Breed,animal.breed_id) if animal and animal.breed_id else None
    weight=db.scalar(select(CattleWeightRecord.weight_kg).where(CattleWeightRecord.cattle_id==listing.cattle_id).order_by(CattleWeightRecord.measured_at.desc()).limit(1))
    age=None
    if animal.date_of_birth:
        today=date.today(); age=(today.year-animal.date_of_birth.year)*12+today.month-animal.date_of_birth.month-(today.day<animal.date_of_birth.day)
    photos=photo_rows(db,listing.id)
    saved=False
    if user_id:
        from app.models.marketplace import MarketplaceFavorite
        saved=db.scalar(select(func.count()).select_from(MarketplaceFavorite).where(MarketplaceFavorite.user_id==user_id,MarketplaceFavorite.listing_id==listing.id))>0
    payload={"id":listing.id,"title":listing.title,"description":listing.description,"asking_price":listing.asking_price,"currency":listing.currency,"location":listing.location,"contact_preference":listing.contact_preference,"status":listing.status,"breed_name":breed.name if breed else None,"sex":animal.sex,"date_of_birth":animal.date_of_birth,"age_months":age,"weight_kg":weight,"published_at":listing.published_at,"updated_at":listing.updated_at,"photos":photos,"saved":saved}
    if seller: payload.update(farm_id=listing.farm_id,cattle_id=listing.cattle_id,seller_user_id=listing.seller_user_id,is_suspended=listing.is_suspended,suspension_reason=listing.suspension_reason,created_at=listing.created_at)
    return payload


def inquiry_payload(db: Session, inquiry: MarketplaceInquiry, viewer_id: UUID, *, include_messages=True):
    listing=db.get(MarketplaceListing,inquiry.listing_id); buyer=db.get(User,inquiry.buyer_user_id)
    seller_view=viewer_id!=inquiry.buyer_user_id; last_read=inquiry.seller_last_read_at if seller_view else inquiry.buyer_last_read_at
    messages=db.scalars(select(MarketplaceInquiryMessage).where(MarketplaceInquiryMessage.inquiry_id==inquiry.id).order_by(MarketplaceInquiryMessage.created_at)).all() if include_messages else []
    unread=any(m.sender_user_id!=viewer_id and (last_read is None or m.created_at>last_read) for m in messages)
    return {"id":inquiry.id,"listing_id":inquiry.listing_id,"listing_title":listing.title,"buyer_user_id":inquiry.buyer_user_id,"buyer_name":buyer.full_name if seller_view else None,"status":inquiry.status,"unread":unread,"created_at":inquiry.created_at,"updated_at":inquiry.updated_at,"messages":messages}


def ensure_message_rate(db: Session, sender_id: UUID):
    now=datetime.now(timezone.utc)
    recent=db.scalar(select(func.max(MarketplaceInquiryMessage.created_at)).where(MarketplaceInquiryMessage.sender_user_id==sender_id))
    if recent and recent>now-timedelta(seconds=2): raise MarketplaceValidationError("Please wait before sending another marketplace message")
    hourly=db.scalar(select(func.count()).select_from(MarketplaceInquiryMessage).where(MarketplaceInquiryMessage.sender_user_id==sender_id,MarketplaceInquiryMessage.created_at>now-timedelta(hours=1))) or 0
    if hourly>=30: raise MarketplaceValidationError("Marketplace message rate limit exceeded")


def sanitize_marketplace_image(content: bytes, content_type: str):
    if content_type=="image/png":
        signature=b"\x89PNG\r\n\x1a\n"
        if not content.startswith(signature): raise MarketplaceValidationError("Invalid PNG image")
        result=bytearray(signature); pos=8; ended=False
        while pos+12<=len(content):
            length=struct.unpack(">I",content[pos:pos+4])[0]; end=pos+12+length
            if end>len(content): raise MarketplaceValidationError("Invalid PNG structure")
            kind=content[pos+4:pos+8]; chunk=content[pos:end]
            if kind in {b"IHDR",b"PLTE",b"IDAT",b"IEND",b"tRNS"}: result.extend(chunk)
            pos=end
            if kind==b"IEND": ended=True; break
        if not ended: raise MarketplaceValidationError("Invalid PNG image")
        return bytes(result),hashlib.sha256(result).hexdigest(),".png"
    if content_type=="image/jpeg":
        if not content.startswith(b"\xff\xd8"): raise MarketplaceValidationError("Invalid JPEG image")
        result=bytearray(b"\xff\xd8"); pos=2
        while pos<len(content):
            if content[pos]!=0xFF: raise MarketplaceValidationError("Invalid JPEG structure")
            marker_start=pos
            while pos<len(content) and content[pos]==0xFF: pos+=1
            if pos>=len(content): raise MarketplaceValidationError("Invalid JPEG image")
            marker=content[pos]; pos+=1
            if marker==0xDA:
                result.extend(content[marker_start:]); break
            if marker==0xD9: result.extend(b"\xff\xd9"); break
            if marker in range(0xD0,0xD8) or marker==0x01: result.extend(content[marker_start:pos]); continue
            if pos+2>len(content): raise MarketplaceValidationError("Invalid JPEG image")
            length=struct.unpack(">H",content[pos:pos+2])[0]; end=pos+length
            if length<2 or end>len(content): raise MarketplaceValidationError("Invalid JPEG image")
            if marker not in range(0xE1,0xF0) and marker!=0xFE: result.extend(content[marker_start:end])
            pos=end
        if len(result)<4: raise MarketplaceValidationError("Invalid JPEG image")
        return bytes(result),hashlib.sha256(result).hexdigest(),".jpg"
    raise MarketplaceValidationError("Marketplace photos must be JPEG or PNG")


def confirm_sale(db: Session, listing: MarketplaceListing, data, actor_id: UUID):
    existing=db.scalar(select(MarketplaceSaleConfirmation).where(MarketplaceSaleConfirmation.farm_id==listing.farm_id,MarketplaceSaleConfirmation.client_request_id==data.client_request_id))
    if existing:
        if existing.listing_id!=listing.id: raise MarketplaceValidationError("Idempotency key belongs to another sale")
        return existing
    if listing.status not in {ListingStatus.PUBLISHED,ListingStatus.RESERVED} or listing.is_suspended: raise MarketplaceValidationError("Only an available, unsuspended listing can be sold")
    animal=db.scalar(select(Cattle).where(Cattle.id==listing.cattle_id,Cattle.farm_id==listing.farm_id).with_for_update())
    if not animal or animal.status!=CattleStatus.ACTIVE: raise MarketplaceValidationError("Cattle is not eligible for sale")
    categories=ensure_categories(db,listing.farm_id,actor_id); tx_id=uuid4(); now=datetime.now(timezone.utc); amount=money(data.agreed_price)
    tx=FinancialTransaction(id=tx_id,farm_id=listing.farm_id,client_request_id=data.client_request_id,transaction_type=FinanceCategoryType.INCOME,category_id=categories["CATTLE_SALES"].id,amount=amount,currency=data.currency,business_date=data.sale_date,status=FinanceTransactionStatus.POSTED,counterparty=data.buyer_reference,reference=f"Marketplace {listing.id}",description="Marketplace cattle sale",notes=data.notes,cattle_id=animal.id,source_type=FinanceSourceType.CATTLE_SALE,source_id=listing.id,created_by_id=actor_id,posted_by_id=actor_id,posted_at=now)
    db.add(tx)
    # The cattle-finance record has a composite FK to the transaction. Flush the
    # parent explicitly because there is no ORM relationship that can infer order.
    db.flush()
    db.add(CattleFinanceTransaction(farm_id=listing.farm_id,client_request_id=data.client_request_id,cattle_id=animal.id,transaction_id=tx.id,transaction_type=CattleTransactionType.SALE,transaction_date=data.sale_date,counterparty=data.buyer_reference,notes=data.notes,created_by_id=actor_id))
    sale=MarketplaceSaleConfirmation(listing_id=listing.id,farm_id=listing.farm_id,client_request_id=data.client_request_id,agreed_price=amount,currency=data.currency,sale_date=data.sale_date,buyer_reference=data.buyer_reference,financial_transaction_id=tx.id,confirmed_by_id=actor_id)
    db.add(sale); history(db,listing,ListingStatus.SOLD,actor_id,"Sale confirmed")
    effective_at=now; validate_operational_lifecycle_time(effective_at=effective_at,latest_event=latest_lifecycle_event(db,farm_id=listing.farm_id,cattle_id=animal.id))
    db.add(CattleLifecycleEvent(cattle_id=animal.id,farm_id=listing.farm_id,previous_status=animal.status,new_status=CattleStatus.SOLD,effective_at=effective_at,reason="Marketplace sale confirmed",actor_id=actor_id)); animal.status=CattleStatus.SOLD
    audit(db,listing,"SOLD","Marketplace sale confirmed and posted to Finance",actor_id); notify(db,listing.seller_user_id,"LISTING_SOLD","Your marketplace listing was marked sold.",listing_id=listing.id)
    return sale
