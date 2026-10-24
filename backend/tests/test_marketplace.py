import base64
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.cattle import AnimalCategory, AnimalSex, Cattle, CattleStatus, Species
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.finance import FinancialTransaction
from app.models.marketplace import MarketplaceAuditEvent, MarketplaceSaleConfirmation
from tests.helpers import authorization_header, create_owned_farm, create_user

pytestmark=pytest.mark.integration
PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def setup(db):
    suffix=uuid.uuid4().hex[:8]; owner=create_user(db,email=f"market-owner-{suffix}@example.com"); farm=create_owned_farm(db,owner=owner,name=f"Market Farm {suffix}")
    animal=Cattle(farm_id=farm.id,tag_number=f"M-{suffix}",normalized_tag=f"m-{suffix}",name="Bella",species=Species.CATTLE,sex=AnimalSex.FEMALE,category=AnimalCategory.COW,date_of_birth=date(2022,1,1),status=CattleStatus.ACTIVE,created_by_id=owner.id); db.add(animal); db.commit()
    buyer=create_user(db,email=f"market-buyer-{suffix}@example.com"); admin=create_user(db,email=f"market-admin-{suffix}@example.com"); admin.is_system_admin=True; db.commit(); return owner,farm,animal,buyer,admin


def create_listing(client,owner,farm,animal):
    response=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings",headers=authorization_header(owner),json={"cattle_id":str(animal.id),"title":"Healthy dairy cow","description":"Productive farm cow available for a verified local buyer.","asking_price":"250000.00","currency":"PKR","location":"Lahore","contact_preference":"IN_APP"}); assert response.status_code==201,response.text
    listing=response.json(); upload=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings/{listing['id']}/photos",headers={**authorization_header(owner),"content-type":"image/png"},params={"filename":"cow.png"},content=PNG); assert upload.status_code==201,upload.text
    return listing,upload.json()


def publish(client,owner,farm,listing_id):
    response=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings/{listing_id}/publish",headers=authorization_header(owner),json={"reason":"Ready for buyers"}); assert response.status_code==200,response.text; return response.json()


def test_listing_photo_search_favorite_inquiry_and_reply(client,db_session):
    owner,farm,animal,buyer,_=setup(db_session); listing,photo=create_listing(client,owner,farm,animal)
    duplicate=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings",headers=authorization_header(owner),json={"cattle_id":str(animal.id),"title":"Duplicate cow","description":"This active duplicate listing must never be accepted by the API.","asking_price":"1","location":"Lahore"}); assert duplicate.status_code==409
    assert client.get("/api/v1/marketplace/listings",headers=authorization_header(buyer)).json()["total"]==0
    published=publish(client,owner,farm,listing["id"]); assert published["status"]=="PUBLISHED"; assert published["photos"][0]["is_primary"] is True
    browse=client.get("/api/v1/marketplace/listings",headers=authorization_header(buyer),params={"search":"dairy","sex":"FEMALE","min_price":"200000","max_price":"300000","location":"Lahore"}); assert browse.status_code==200,browse.text; assert browse.json()["total"]==1; assert "farm_id" not in browse.json()["items"][0]; assert "cattle_id" not in browse.json()["items"][0]
    image=client.get(f"/api/v1/marketplace/listings/{listing['id']}/photos/{photo['id']}/content",headers=authorization_header(buyer)); assert image.status_code==200; assert image.headers["x-content-type-options"]=="nosniff"
    assert client.post(f"/api/v1/marketplace/listings/{listing['id']}/favorite",headers=authorization_header(buyer)).status_code==201
    assert client.post(f"/api/v1/marketplace/listings/{listing['id']}/favorite",headers=authorization_header(buyer)).status_code==409
    assert client.get("/api/v1/marketplace/saved",headers=authorization_header(buyer)).json()[0]["saved"] is True
    inquiry=client.post(f"/api/v1/marketplace/listings/{listing['id']}/inquiries",headers=authorization_header(buyer),json={"message":"Is this cow still available for inspection?"}); assert inquiry.status_code==201,inquiry.text; inquiry_id=inquiry.json()["id"]
    own=client.post(f"/api/v1/marketplace/listings/{listing['id']}/inquiries",headers=authorization_header(owner),json={"message":"Invalid self inquiry message"}); assert own.status_code==422
    reply=client.post(f"/api/v1/marketplace/inquiries/{inquiry_id}/messages",headers=authorization_header(owner),json={"body":"Yes, please propose a suitable inspection time."}); assert reply.status_code==201,reply.text
    thread=client.get(f"/api/v1/marketplace/inquiries/{inquiry_id}",headers=authorization_header(buyer)); assert len(thread.json()["messages"])==2
    closed=client.post(f"/api/v1/marketplace/inquiries/{inquiry_id}/close",headers=authorization_header(buyer)); assert closed.status_code==200; assert closed.json()["status"]=="CLOSED"
    blocked=client.post(f"/api/v1/marketplace/inquiries/{inquiry_id}/messages",headers=authorization_header(owner),json={"body":"This must be rejected while closed."}); assert blocked.status_code==422
    reopened=client.post(f"/api/v1/marketplace/inquiries/{inquiry_id}/reopen",headers=authorization_header(owner)); assert reopened.status_code==200; assert reopened.json()["status"]=="OPEN"


def test_sale_confirmation_is_idempotent_and_posts_once(client,db_session):
    owner,farm,animal,buyer,_=setup(db_session); listing,_=create_listing(client,owner,farm,animal); publish(client,owner,farm,listing["id"]); request_id=uuid.uuid4(); payload={"client_request_id":str(request_id),"agreed_price":"240000","currency":"PKR","sale_date":date.today().isoformat(),"buyer_reference":"Verified Buyer","notes":"Payment due under private agreement"}
    first=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings/{listing['id']}/sales",headers=authorization_header(owner),json=payload); assert first.status_code==201,first.text
    second=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings/{listing['id']}/sales",headers=authorization_header(owner),json=payload); assert second.status_code==201,second.text; assert second.json()["id"]==first.json()["id"]
    db_session.expire_all(); assert db_session.get(Cattle,animal.id).status==CattleStatus.SOLD
    transactions=db_session.scalars(select(FinancialTransaction).where(FinancialTransaction.farm_id==farm.id,FinancialTransaction.source_id==uuid.UUID(listing["id"]))).all(); assert len(transactions)==1; assert transactions[0].amount==Decimal("240000.00")
    assert db_session.scalar(select(MarketplaceSaleConfirmation).where(MarketplaceSaleConfirmation.listing_id==uuid.UUID(listing["id"]))) is not None
    assert client.get("/api/v1/marketplace/listings",headers=authorization_header(buyer)).json()["total"]==0


def test_worker_and_veterinarian_cannot_manage_or_sell(client,db_session):
    owner,farm,animal,buyer,_=setup(db_session)
    for role in [FarmRole.WORKER,FarmRole.VETERINARIAN]:
        user=create_user(db_session,email=f"{role.value.lower()}-{uuid.uuid4().hex}@example.com"); db_session.add(FarmMember(farm_id=farm.id,user_id=user.id,role=role,status=MemberStatus.ACTIVE)); db_session.commit()
        assert client.get("/api/v1/marketplace/listings",headers=authorization_header(user)).status_code==200
        assert client.get(f"/api/v1/farms/{farm.id}/marketplace/listings",headers=authorization_header(user)).status_code==403
        denied=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings",headers=authorization_header(user),json={"cattle_id":str(animal.id),"title":"Not allowed","description":"Worker cannot create a private seller listing for this farm.","asking_price":"100","location":"Farm"}); assert denied.status_code==403


def test_marketplace_farm_isolation_and_price_validation(client,db_session):
    owner,farm,animal,_,_=setup(db_session); listing,_=create_listing(client,owner,farm,animal)
    other_owner,other_farm,_,_,_=setup(db_session)
    cross=client.patch(f"/api/v1/farms/{other_farm.id}/marketplace/listings/{listing['id']}",headers=authorization_header(other_owner),json={"title":"Cross-farm edit attempt"})
    assert cross.status_code==404
    invalid=client.post(f"/api/v1/farms/{farm.id}/marketplace/listings",headers=authorization_header(owner),json={"cattle_id":str(uuid.uuid4()),"title":"Invalid price listing","description":"This listing has an invalid negative asking price.","asking_price":"-1","location":"Lahore"})
    assert invalid.status_code==422


def test_reporting_and_system_admin_moderation_are_audited(client,db_session):
    owner,farm,animal,buyer,admin=setup(db_session); listing,_=create_listing(client,owner,farm,animal); publish(client,owner,farm,listing["id"])
    report=client.post(f"/api/v1/marketplace/listings/{listing['id']}/reports",headers=authorization_header(buyer),json={"reason":"MISLEADING","details":"The listing description needs seller verification."}); assert report.status_code==201,report.text
    assert client.get("/api/v1/marketplace/moderation/reports",headers=authorization_header(owner)).status_code==403
    queue=client.get("/api/v1/marketplace/moderation/reports",headers=authorization_header(admin)); assert queue.status_code==200; assert len(queue.json())==1
    action=client.post(f"/api/v1/marketplace/moderation/listings/{listing['id']}",headers=authorization_header(admin),json={"action":"SUSPEND","reason":"Temporarily hidden during review","report_id":report.json()["id"]}); assert action.status_code==200,action.text; assert action.json()["is_suspended"] is True
    assert client.get("/api/v1/marketplace/listings",headers=authorization_header(buyer)).json()["total"]==0
    assert db_session.scalar(select(MarketplaceAuditEvent).where(MarketplaceAuditEvent.entity_id==uuid.UUID(listing["id"]),MarketplaceAuditEvent.action=="MODERATED")) is not None
