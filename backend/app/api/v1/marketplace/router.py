from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import get_effective_permissions, require_farm_permission
from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import AnimalSex, Breed, Cattle, CattleStatus, CattleWeightRecord
from app.models.farm import Farm
from app.models.farm_member import FarmMember, MemberStatus
from app.models.marketplace import *
from app.models.user import User
from app.schemas.marketplace import *
from app.services.marketplace import (MarketplaceValidationError, audit,
    confirm_sale, ensure_message_rate, history, inquiry_payload,
    listing_or_error, listing_payload, notify, photo_rows,
    sanitize_marketplace_image)
from app.services.media_storage import MediaStorage, detect_image_content_type, get_media_storage, validate_original_filename

router=APIRouter(tags=["Cattle Marketplace"])
global_router=APIRouter(prefix="/marketplace")
farm_router=APIRouter(prefix="/farms/{farm_id}/marketplace")


def invalid(error): return HTTPException(422,str(error))
def commit(db, conflict="Duplicate or conflicting marketplace record"):
    try: db.commit()
    except IntegrityError: db.rollback(); raise HTTPException(409,conflict) from None
    except SQLAlchemyError: db.rollback(); raise HTTPException(500,"Marketplace operation failed") from None


def admin(user: User=Depends(get_current_user)):
    if not user.is_system_admin: raise HTTPException(403,"System administrator access required")
    return user


def member_access(db: Session, farm_id: UUID, user: User):
    farm=db.get(Farm,farm_id); membership=db.scalar(select(FarmMember).where(FarmMember.farm_id==farm_id,FarmMember.user_id==user.id,FarmMember.status==MemberStatus.ACTIVE))
    return FarmAccess(farm=farm,membership=membership) if farm and membership else None


def can_manage_inquiry(db: Session, inquiry: MarketplaceInquiry, user: User):
    if inquiry.buyer_user_id==user.id: return "buyer"
    access=member_access(db,inquiry.farm_id,user)
    if access and Permission.MARKETPLACE_INQUIRY_MANAGE in get_effective_permissions(db,access): return "seller"
    raise HTTPException(404,"Marketplace inquiry not found")


def visible_listing(db: Session, listing_id: UUID, user: User):
    listing=db.get(MarketplaceListing,listing_id)
    if not listing: raise HTTPException(404,"Marketplace listing not found")
    public=listing.status in {ListingStatus.PUBLISHED,ListingStatus.RESERVED,ListingStatus.SOLD} and not listing.is_suspended
    saved=db.scalar(select(MarketplaceFavorite.id).where(MarketplaceFavorite.user_id==user.id,MarketplaceFavorite.listing_id==listing.id))
    reported=user.is_system_admin and db.scalar(select(MarketplaceListingReport.id).where(MarketplaceListingReport.listing_id==listing.id).limit(1))
    if not public and listing.seller_user_id!=user.id and not saved and not reported: raise HTTPException(404,"Marketplace listing not found")
    return listing


@global_router.get("/listings",response_model=ListingPage)
def browse_listings(search: str|None=None, breed_id: UUID|None=None, sex: AnimalSex|None=None, min_age_months: int|None=Query(None,ge=0,le=360), max_age_months: int|None=Query(None,ge=0,le=360), min_price: Decimal|None=Query(None,ge=0), max_price: Decimal|None=Query(None,ge=0), location: str|None=None, min_weight: Decimal|None=Query(None,ge=0), max_weight: Decimal|None=Query(None,ge=0), sort: str=Query("newest",pattern="^(newest|price_asc|price_desc)$"), limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    latest_weight=select(CattleWeightRecord.weight_kg).where(CattleWeightRecord.cattle_id==MarketplaceListing.cattle_id).order_by(CattleWeightRecord.measured_at.desc()).limit(1).scalar_subquery()
    q=select(MarketplaceListing).join(Cattle,Cattle.id==MarketplaceListing.cattle_id).outerjoin(Breed,Breed.id==Cattle.breed_id).where(MarketplaceListing.status.in_([ListingStatus.PUBLISHED,ListingStatus.RESERVED]),MarketplaceListing.is_suspended.is_(False),Cattle.status==CattleStatus.ACTIVE)
    if search: q=q.where(or_(MarketplaceListing.title.ilike(f"%{search.strip()}%"),MarketplaceListing.description.ilike(f"%{search.strip()}%"),MarketplaceListing.location.ilike(f"%{search.strip()}%"),Breed.name.ilike(f"%{search.strip()}%")))
    if breed_id: q=q.where(Cattle.breed_id==breed_id)
    if sex: q=q.where(Cattle.sex==sex)
    if location: q=q.where(MarketplaceListing.location.ilike(f"%{location.strip()}%"))
    if min_price is not None: q=q.where(MarketplaceListing.asking_price>=min_price)
    if max_price is not None: q=q.where(MarketplaceListing.asking_price<=max_price)
    today=date.today()
    if min_age_months is not None: q=q.where(Cattle.date_of_birth<=today-timedelta(days=min_age_months*30))
    if max_age_months is not None: q=q.where(Cattle.date_of_birth>=today-timedelta(days=(max_age_months+1)*31))
    if min_weight is not None: q=q.where(latest_weight>=min_weight)
    if max_weight is not None: q=q.where(latest_weight<=max_weight)
    if min_price is not None and max_price is not None and min_price>max_price: raise HTTPException(422,"min_price cannot exceed max_price")
    total=db.scalar(select(func.count()).select_from(q.subquery())) or 0
    order=MarketplaceListing.asking_price.asc() if sort=="price_asc" else MarketplaceListing.asking_price.desc() if sort=="price_desc" else MarketplaceListing.published_at.desc()
    rows=db.scalars(q.order_by(order,MarketplaceListing.id).limit(limit).offset(offset)).all()
    return {"items":[listing_payload(db,row,user_id=current_user.id) for row in rows],"total":total,"limit":limit,"offset":offset}


@global_router.get("/listings/{listing_id}",response_model=PublicListingResponse)
def listing_detail(listing_id: UUID, current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    listing=visible_listing(db,listing_id,current_user); return listing_payload(db,listing,user_id=current_user.id)


@global_router.get("/listings/{listing_id}/photos/{photo_id}/content")
def photo_content(listing_id: UUID, photo_id: UUID, current_user: User=Depends(get_current_user), db: Session=Depends(get_db), storage: MediaStorage=Depends(get_media_storage)):
    visible_listing(db,listing_id,current_user); photo=db.scalar(select(MarketplaceListingPhoto).where(MarketplaceListingPhoto.id==photo_id,MarketplaceListingPhoto.listing_id==listing_id,MarketplaceListingPhoto.removed_at.is_(None)))
    if not photo: raise HTTPException(404,"Marketplace photo not found")
    try: path=storage.resolve(photo.storage_key)
    except FileNotFoundError: raise HTTPException(404,"Marketplace photo content not found") from None
    return FileResponse(path=path,media_type=photo.content_type,headers={"Cache-Control":"private, max-age=300","X-Content-Type-Options":"nosniff"})


@global_router.post("/listings/{listing_id}/inquiries",response_model=InquiryResponse,status_code=201)
def create_inquiry(listing_id: UUID, data: InquiryCreate, current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    listing=visible_listing(db,listing_id,current_user)
    if listing.status not in {ListingStatus.PUBLISHED,ListingStatus.RESERVED} or listing.is_suspended: raise HTTPException(422,"Listing is not accepting inquiries")
    if member_access(db,listing.farm_id,current_user): raise HTTPException(422,"Farm members cannot inquire about their own farm listing")
    try: ensure_message_rate(db,current_user.id)
    except MarketplaceValidationError as error: raise HTTPException(429,str(error)) from None
    inquiry=MarketplaceInquiry(id=uuid4(),listing_id=listing.id,farm_id=listing.farm_id,buyer_user_id=current_user.id); db.add(inquiry); db.add(MarketplaceInquiryMessage(inquiry_id=inquiry.id,sender_user_id=current_user.id,body=data.message)); notify(db,listing.seller_user_id,"NEW_INQUIRY","A buyer sent a new marketplace inquiry.",listing_id=listing.id,inquiry_id=inquiry.id); audit(db,listing,"INQUIRY_CREATED","Buyer inquiry created",current_user.id); commit(db); db.refresh(inquiry); return inquiry_payload(db,inquiry,current_user.id)


@global_router.get("/inquiries",response_model=list[InquiryResponse])
def buyer_inquiries(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    rows=db.scalars(select(MarketplaceInquiry).where(MarketplaceInquiry.buyer_user_id==current_user.id).order_by(MarketplaceInquiry.updated_at.desc()).limit(limit).offset(offset)).all(); return [inquiry_payload(db,row,current_user.id) for row in rows]


@global_router.get("/inquiries/{inquiry_id}",response_model=InquiryResponse)
def inquiry_detail(inquiry_id: UUID,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    row=db.get(MarketplaceInquiry,inquiry_id)
    if not row: raise HTTPException(404,"Marketplace inquiry not found")
    role=can_manage_inquiry(db,row,current_user); now=datetime.now(timezone.utc)
    if role=="buyer": row.buyer_last_read_at=now
    else: row.seller_last_read_at=now
    commit(db); return inquiry_payload(db,row,current_user.id)


@global_router.post("/inquiries/{inquiry_id}/messages",response_model=InquiryMessageResponse,status_code=201)
def send_message(inquiry_id: UUID,data: InquiryMessageCreate,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    inquiry=db.scalar(select(MarketplaceInquiry).where(MarketplaceInquiry.id==inquiry_id).with_for_update())
    if not inquiry: raise HTTPException(404,"Marketplace inquiry not found")
    role=can_manage_inquiry(db,inquiry,current_user)
    if inquiry.status!=InquiryStatus.OPEN: raise HTTPException(422,"Inquiry is closed")
    try: ensure_message_rate(db,current_user.id)
    except MarketplaceValidationError as error: raise HTTPException(429,str(error)) from None
    message=MarketplaceInquiryMessage(inquiry_id=inquiry.id,sender_user_id=current_user.id,body=data.body); db.add(message); inquiry.updated_at=datetime.now(timezone.utc); listing=db.get(MarketplaceListing,inquiry.listing_id)
    recipient=inquiry.buyer_user_id if role=="seller" else listing.seller_user_id; notify(db,recipient,"INQUIRY_RESPONSE","A marketplace inquiry has a new response.",listing_id=listing.id,inquiry_id=inquiry.id); audit(db,listing,"MESSAGE_SENT","Inquiry response sent",current_user.id); commit(db); db.refresh(message); return message


@global_router.post("/inquiries/{inquiry_id}/close",response_model=InquiryResponse)
def close_inquiry(inquiry_id: UUID,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    inquiry=db.scalar(select(MarketplaceInquiry).where(MarketplaceInquiry.id==inquiry_id).with_for_update())
    if not inquiry: raise HTTPException(404,"Marketplace inquiry not found")
    can_manage_inquiry(db,inquiry,current_user)
    inquiry.status=InquiryStatus.CLOSED; inquiry.closed_at=datetime.now(timezone.utc); inquiry.updated_at=inquiry.closed_at
    listing=db.get(MarketplaceListing,inquiry.listing_id); audit(db,listing,"INQUIRY_CLOSED","Marketplace inquiry closed",current_user.id)
    commit(db); return inquiry_payload(db,inquiry,current_user.id)


@global_router.post("/inquiries/{inquiry_id}/reopen",response_model=InquiryResponse)
def reopen_inquiry(inquiry_id: UUID,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    inquiry=db.scalar(select(MarketplaceInquiry).where(MarketplaceInquiry.id==inquiry_id).with_for_update())
    if not inquiry: raise HTTPException(404,"Marketplace inquiry not found")
    can_manage_inquiry(db,inquiry,current_user)
    inquiry.status=InquiryStatus.OPEN; inquiry.closed_at=None; inquiry.updated_at=datetime.now(timezone.utc)
    listing=db.get(MarketplaceListing,inquiry.listing_id); audit(db,listing,"INQUIRY_REOPENED","Marketplace inquiry reopened",current_user.id)
    commit(db); return inquiry_payload(db,inquiry,current_user.id)


@global_router.post("/listings/{listing_id}/favorite",status_code=201)
def save_listing(listing_id: UUID,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    visible_listing(db,listing_id,current_user); row=MarketplaceFavorite(user_id=current_user.id,listing_id=listing_id); db.add(row); commit(db,"Listing is already saved"); return {"saved":True}


@global_router.delete("/listings/{listing_id}/favorite",status_code=204)
def unsave_listing(listing_id: UUID,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    row=db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.user_id==current_user.id,MarketplaceFavorite.listing_id==listing_id))
    if row: db.delete(row); commit(db)
    return None


@global_router.get("/saved",response_model=list[PublicListingResponse])
def saved_listings(current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    rows=db.scalars(select(MarketplaceListing).join(MarketplaceFavorite,MarketplaceFavorite.listing_id==MarketplaceListing.id).where(MarketplaceFavorite.user_id==current_user.id).order_by(MarketplaceFavorite.created_at.desc())).all(); return [listing_payload(db,row,user_id=current_user.id) for row in rows]


@global_router.post("/listings/{listing_id}/reports",response_model=ReportResponse,status_code=201)
def report_listing(listing_id: UUID,data: ReportCreate,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    listing=visible_listing(db,listing_id,current_user)
    if listing.seller_user_id==current_user.id: raise HTTPException(422,"You cannot report your own listing")
    row=MarketplaceListingReport(listing_id=listing.id,reporter_user_id=current_user.id,reason=data.reason,details=data.details); db.add(row); audit(db,listing,"REPORTED",f"Listing reported: {data.reason.value}",current_user.id); commit(db,"You have already reported this listing"); db.refresh(row); return row


@global_router.get("/notifications",response_model=list[NotificationResponse])
def notifications(unread_only: bool=False,limit: int=Query(50,ge=1,le=100),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    q=select(MarketplaceNotification).where(MarketplaceNotification.user_id==current_user.id)
    if unread_only: q=q.where(MarketplaceNotification.read_at.is_(None))
    return db.scalars(q.order_by(MarketplaceNotification.created_at.desc()).limit(limit)).all()


@global_router.post("/notifications/{notification_id}/read",response_model=NotificationResponse)
def read_notification(notification_id: UUID,current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    row=db.scalar(select(MarketplaceNotification).where(MarketplaceNotification.id==notification_id,MarketplaceNotification.user_id==current_user.id))
    if not row: raise HTTPException(404,"Marketplace notification not found")
    row.read_at=datetime.now(timezone.utc); commit(db); db.refresh(row); return row


@farm_router.get("/listings",response_model=list[SellerListingResponse])
def seller_listings(farm_id: UUID,listing_status: ListingStatus|None=None,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    q=select(MarketplaceListing).where(MarketplaceListing.farm_id==farm_id)
    if listing_status: q=q.where(MarketplaceListing.status==listing_status)
    rows=db.scalars(q.order_by(MarketplaceListing.updated_at.desc())).all(); return [listing_payload(db,row,user_id=current_user.id,seller=True) for row in rows]


@farm_router.post("/listings",response_model=SellerListingResponse,status_code=201)
def create_listing(farm_id: UUID,data: ListingCreate,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    animal=db.scalar(select(Cattle).where(Cattle.id==data.cattle_id,Cattle.farm_id==farm_id).with_for_update())
    if not animal: raise HTTPException(404,"Cattle not found")
    if animal.status!=CattleStatus.ACTIVE: raise HTTPException(422,"Only active cattle may be listed")
    row=MarketplaceListing(id=uuid4(),farm_id=farm_id,seller_user_id=current_user.id,**data.model_dump()); db.add(row); db.add(MarketplaceListingStatusHistory(listing_id=row.id,previous_status=None,new_status=ListingStatus.DRAFT,reason="Listing created",actor_id=current_user.id)); audit(db,row,"CREATED","Marketplace draft created",current_user.id); commit(db,"Cattle already has an active marketplace listing"); db.refresh(row); return listing_payload(db,row,user_id=current_user.id,seller=True)


@farm_router.patch("/listings/{listing_id}",response_model=SellerListingResponse)
def update_listing(farm_id: UUID,listing_id: UUID,data: ListingUpdate,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    try: row=listing_or_error(db,listing_id,farm_id=farm_id,lock=True)
    except MarketplaceValidationError as error: raise HTTPException(404,str(error)) from None
    if row.status not in {ListingStatus.DRAFT,ListingStatus.PUBLISHED}: raise HTTPException(422,"Only draft or published listings can be edited")
    if row.is_suspended: raise HTTPException(422,"Suspended listings cannot be edited")
    for key,value in data.model_dump(exclude_unset=True).items(): setattr(row,key,value)
    audit(db,row,"UPDATED","Marketplace listing updated",current_user.id); commit(db); db.refresh(row); return listing_payload(db,row,user_id=current_user.id,seller=True)


def change_status(farm_id,listing_id,target,data,actor,db):
    try: row=listing_or_error(db,listing_id,farm_id=farm_id,lock=True)
    except MarketplaceValidationError as error: raise HTTPException(404,str(error)) from None
    allowed={ListingStatus.PUBLISHED:{ListingStatus.DRAFT,ListingStatus.ARCHIVED},ListingStatus.RESERVED:{ListingStatus.PUBLISHED},ListingStatus.ARCHIVED:{ListingStatus.DRAFT,ListingStatus.PUBLISHED,ListingStatus.RESERVED}}
    if row.status not in allowed[target]: raise HTTPException(422,f"Cannot change {row.status.value} listing to {target.value}")
    if target==ListingStatus.PUBLISHED:
        animal=db.scalar(select(Cattle).where(Cattle.id==row.cattle_id,Cattle.farm_id==farm_id).with_for_update())
        if not animal or animal.status!=CattleStatus.ACTIVE: raise HTTPException(422,"Cattle is not eligible for publication")
        if row.is_suspended: raise HTTPException(422,"Suspended listing cannot be published")
        if not photo_rows(db,row.id): raise HTTPException(422,"At least one listing photo is required before publication")
    history(db,row,target,actor.id,data.reason); audit(db,row,target.value,f"Listing changed to {target.value}",actor.id); notify(db,row.seller_user_id,f"LISTING_{target.value}",f"Your listing is now {target.value.lower()}.",listing_id=row.id); commit(db); db.refresh(row); return listing_payload(db,row,user_id=actor.id,seller=True)


@farm_router.post("/listings/{listing_id}/publish",response_model=SellerListingResponse)
def publish_listing(farm_id: UUID,listing_id: UUID,data: StatusChange,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)): return change_status(farm_id,listing_id,ListingStatus.PUBLISHED,data,current_user,db)
@farm_router.post("/listings/{listing_id}/reserve",response_model=SellerListingResponse)
def reserve_listing(farm_id: UUID,listing_id: UUID,data: StatusChange,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)): return change_status(farm_id,listing_id,ListingStatus.RESERVED,data,current_user,db)
@farm_router.post("/listings/{listing_id}/archive",response_model=SellerListingResponse)
def archive_listing(farm_id: UUID,listing_id: UUID,data: StatusChange,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)): return change_status(farm_id,listing_id,ListingStatus.ARCHIVED,data,current_user,db)


async def limited_body(request,maximum):
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>maximum: raise HTTPException(413,"Image is too large")
        data.extend(chunk)
    return bytes(data)


@farm_router.post("/listings/{listing_id}/photos",response_model=PhotoResponse,status_code=201)
async def upload_photo(farm_id: UUID,listing_id: UUID,request: Request,filename: str=Query(min_length=1,max_length=255),is_primary: bool=False,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db),storage: MediaStorage=Depends(get_media_storage)):
    try: listing=listing_or_error(db,listing_id,farm_id=farm_id)
    except MarketplaceValidationError as error: raise HTTPException(404,str(error)) from None
    if listing.status in {ListingStatus.SOLD,ListingStatus.ARCHIVED}: raise HTTPException(422,"Photos cannot be added to inactive listings")
    if len(photo_rows(db,listing.id))>=10: raise HTTPException(422,"A listing may contain at most 10 photos")
    try: original=validate_original_filename(filename)
    except ValueError as error: raise HTTPException(422,str(error)) from None
    content=await limited_body(request,get_settings().CATTLE_MEDIA_MAX_BYTES)
    if not content: raise HTTPException(422,"Image content is required")
    try: detected=detect_image_content_type(content); clean,digest,extension=sanitize_marketplace_image(content,detected)
    except (ValueError,MarketplaceValidationError) as error: raise HTTPException(422,str(error)) from None
    declared=request.headers.get("content-type","").split(";",1)[0].lower()
    if declared not in {detected,"application/octet-stream"}: raise HTTPException(422,"Declared content type does not match image content")
    existing=db.scalar(select(MarketplaceListingPhoto).where(MarketplaceListingPhoto.listing_id==listing.id,MarketplaceListingPhoto.content_sha256==digest))
    if existing: raise HTTPException(409,"Duplicate listing photo")
    current=photo_rows(db,listing.id); primary=is_primary or not current
    if primary:
        for item in current: item.is_primary=False
    photo_id=uuid4(); key=f"marketplace/{farm_id}/{listing.id}/{photo_id}{extension}"; row=MarketplaceListingPhoto(id=photo_id,listing_id=listing.id,farm_id=farm_id,storage_key=key,original_filename=original,content_type=detected,content_sha256=digest,size_bytes=len(clean),is_primary=primary,display_order=len(current),uploaded_by_id=current_user.id)
    try: storage.save(key,clean); db.add(row); audit(db,listing,"PHOTO_UPLOADED","Marketplace photo uploaded",current_user.id); db.commit(); db.refresh(row); return row
    except Exception: db.rollback(); storage.delete(key); raise HTTPException(500,"Could not store marketplace photo") from None


@farm_router.post("/listings/{listing_id}/photos/{photo_id}/primary",response_model=PhotoResponse)
def set_primary(farm_id: UUID,listing_id: UUID,photo_id: UUID,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    try: listing=listing_or_error(db,listing_id,farm_id=farm_id,lock=True)
    except MarketplaceValidationError as error: raise HTTPException(404,str(error)) from None
    photos=photo_rows(db,listing.id); row=next((p for p in photos if p.id==photo_id),None)
    if not row: raise HTTPException(404,"Marketplace photo not found")
    for item in photos: item.is_primary=item.id==row.id
    audit(db,listing,"PRIMARY_PHOTO","Primary marketplace photo changed",current_user.id); commit(db); db.refresh(row); return row


@farm_router.delete("/listings/{listing_id}/photos/{photo_id}",status_code=204)
def remove_photo(farm_id: UUID,listing_id: UUID,photo_id: UUID,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db),storage: MediaStorage=Depends(get_media_storage)):
    try: listing=listing_or_error(db,listing_id,farm_id=farm_id,lock=True)
    except MarketplaceValidationError as error: raise HTTPException(404,str(error)) from None
    photos=photo_rows(db,listing.id); row=next((p for p in photos if p.id==photo_id),None)
    if not row: raise HTTPException(404,"Marketplace photo not found")
    row.removed_at=datetime.now(timezone.utc); row.removed_by_id=current_user.id
    if row.is_primary:
        replacement=next((p for p in photos if p.id!=row.id),None)
        if replacement: replacement.is_primary=True
    audit(db,listing,"PHOTO_REMOVED","Marketplace photo removed",current_user.id); commit(db)
    try: storage.delete(row.storage_key)
    except OSError: pass
    return None


@farm_router.get("/inquiries",response_model=list[InquiryResponse])
def seller_inquiries(farm_id: UUID,limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0),access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_INQUIRY_MANAGE)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    rows=db.scalars(select(MarketplaceInquiry).where(MarketplaceInquiry.farm_id==farm_id).order_by(MarketplaceInquiry.updated_at.desc()).limit(limit).offset(offset)).all(); return [inquiry_payload(db,row,current_user.id) for row in rows]


@farm_router.post("/listings/{listing_id}/sales",response_model=SaleResponse,status_code=201)
def complete_sale(farm_id: UUID,listing_id: UUID,data: SaleConfirm,access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_SALE_CONFIRM)),current_user: User=Depends(get_current_user),db: Session=Depends(get_db)):
    try: listing=listing_or_error(db,listing_id,farm_id=farm_id,lock=True); sale=confirm_sale(db,listing,data,current_user.id); commit(db,"Sale was already confirmed or the idempotency key conflicts"); db.refresh(sale); return sale
    except MarketplaceValidationError as error: db.rollback(); raise invalid(error)


@farm_router.get("/reports",response_model=SellerMetrics)
def seller_metrics(farm_id: UUID,start: date|None=None,end: date|None=None,currency: str="PKR",access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),db: Session=Depends(get_db)):
    if start and end and start>end: raise HTTPException(422,"start cannot be after end")
    counts=dict(db.execute(select(MarketplaceListing.status,func.count()).where(MarketplaceListing.farm_id==farm_id).group_by(MarketplaceListing.status)).all()); inquiry_count=db.scalar(select(func.count()).select_from(MarketplaceInquiry).where(MarketplaceInquiry.farm_id==farm_id)) or 0
    q=select(MarketplaceSaleConfirmation).where(MarketplaceSaleConfirmation.farm_id==farm_id,MarketplaceSaleConfirmation.currency==currency.upper())
    if start: q=q.where(MarketplaceSaleConfirmation.sale_date>=start)
    if end: q=q.where(MarketplaceSaleConfirmation.sale_date<=end)
    sales=db.scalars(q).all(); published=sum(counts.get(s,0) for s in [ListingStatus.PUBLISHED,ListingStatus.RESERVED,ListingStatus.SOLD,ListingStatus.ARCHIVED]); sold=counts.get(ListingStatus.SOLD,0); rate=(Decimal(sold*100)/Decimal(published)).quantize(Decimal("0.01")) if published else Decimal("0.00")
    return {"active_listings":counts.get(ListingStatus.PUBLISHED,0)+counts.get(ListingStatus.RESERVED,0),"draft_listings":counts.get(ListingStatus.DRAFT,0),"archived_listings":counts.get(ListingStatus.ARCHIVED,0),"sold_listings":sold,"inquiry_count":inquiry_count,"sale_count":len(sales),"conversion_rate":rate,"sales_total":sum((s.agreed_price for s in sales),Decimal("0")),"currency":currency.upper()}


@farm_router.get("/audit")
def marketplace_audit(farm_id: UUID,limit: int=Query(100,ge=1,le=500),access: FarmAccess=Depends(require_farm_permission(Permission.MARKETPLACE_LISTING_MANAGE)),db: Session=Depends(get_db)):
    return db.scalars(select(MarketplaceAuditEvent).where(MarketplaceAuditEvent.farm_id==farm_id).order_by(MarketplaceAuditEvent.created_at.desc()).limit(limit)).all()


@global_router.get("/moderation/reports",response_model=list[ReportResponse])
def moderation_queue(report_status: ListingReportStatus=ListingReportStatus.OPEN,user: User=Depends(admin),db: Session=Depends(get_db)):
    return db.scalars(select(MarketplaceListingReport).where(MarketplaceListingReport.status==report_status).order_by(MarketplaceListingReport.created_at)).all()


@global_router.post("/moderation/listings/{listing_id}")
def moderate_listing(listing_id: UUID,data: ModerationCreate,user: User=Depends(admin),db: Session=Depends(get_db)):
    listing=db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id).with_for_update())
    if not listing: raise HTTPException(404,"Marketplace listing not found")
    if listing.seller_user_id==user.id: raise HTTPException(409,"Moderator cannot act on their own listing")
    if data.action in {ModerationActionType.SUSPEND,ModerationActionType.REMOVE}: listing.is_suspended=True; listing.suspension_reason=data.reason
    elif data.action==ModerationActionType.RESTORE: listing.is_suspended=False; listing.suspension_reason=None
    elif data.action!=ModerationActionType.DISMISS_REPORT: raise HTTPException(422,"Unsupported moderation action")
    report=None
    if data.report_id:
        report=db.scalar(select(MarketplaceListingReport).where(MarketplaceListingReport.id==data.report_id,MarketplaceListingReport.listing_id==listing.id).with_for_update())
        if not report: raise HTTPException(404,"Marketplace report not found")
        report.status=ListingReportStatus.DISMISSED if data.action==ModerationActionType.DISMISS_REPORT else ListingReportStatus.ACTIONED; report.resolved_by_id=user.id; report.resolved_at=datetime.now(timezone.utc)
    db.add(MarketplaceModerationAction(listing_id=listing.id,report_id=report.id if report else None,action=data.action,reason=data.reason,actor_user_id=user.id)); audit(db,listing,"MODERATED",f"Moderation action: {data.action.value}",user.id); notify(db,listing.seller_user_id,"LISTING_MODERATED",f"Marketplace moderation action: {data.action.value}.",listing_id=listing.id); commit(db); return {"listing_id":listing.id,"action":data.action,"is_suspended":listing.is_suspended}


router.include_router(global_router); router.include_router(farm_router)
