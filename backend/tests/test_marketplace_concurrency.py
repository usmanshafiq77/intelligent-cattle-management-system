import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cattle import AnimalCategory, AnimalSex, Cattle, CattleStatus, Species
from app.models.farm import Farm
from app.models.finance import FinancialTransaction
from app.models.marketplace import ContactPreference, ListingStatus, MarketplaceListing, MarketplaceSaleConfirmation
from app.models.user import User, UserStatus
from app.services.marketplace import MarketplaceValidationError, confirm_sale

pytestmark=pytest.mark.integration


def test_concurrent_sale_confirmations_post_only_once(pg_engine):
    user_id,farm_id,cattle_id,listing_id=[uuid.uuid4() for _ in range(4)]
    with Session(pg_engine) as db:
        db.add(User(id=user_id,full_name="Concurrent Seller",email=f"market-concurrent-{user_id.hex}@example.com",password_hash="x",status=UserStatus.ACTIVE,is_system_admin=False,email_verified_at=datetime.now(timezone.utc)))
        db.flush()
        db.add(Farm(id=farm_id,name="Concurrent Marketplace Farm",owner_id=user_id))
        db.flush()
        db.add(Cattle(id=cattle_id,farm_id=farm_id,tag_number=f"MC-{cattle_id.hex[:8]}",normalized_tag=f"mc-{cattle_id.hex[:8]}",species=Species.CATTLE,sex=AnimalSex.FEMALE,category=AnimalCategory.COW,status=CattleStatus.ACTIVE,created_by_id=user_id))
        db.flush()
        db.add(MarketplaceListing(id=listing_id,farm_id=farm_id,cattle_id=cattle_id,seller_user_id=user_id,title="Concurrent sale cow",description="A valid cattle listing used to verify sale locking.",asking_price=Decimal("200000"),currency="PKR",location="Lahore",contact_preference=ContactPreference.IN_APP,status=ListingStatus.PUBLISHED,published_at=datetime.now(timezone.utc)))
        db.commit()

    barrier=Barrier(2)
    def sell():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            listing=db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id).with_for_update())
            data=SimpleNamespace(client_request_id=uuid.uuid4(),agreed_price=Decimal("190000"),currency="PKR",sale_date=date.today(),buyer_reference="Concurrent buyer",notes=None)
            try:
                confirm_sale(db,listing,data,user_id); db.commit(); return "confirmed"
            except (MarketplaceValidationError,IntegrityError):
                db.rollback(); return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=[future.result(timeout=20) for future in [pool.submit(sell),pool.submit(sell)]]
    assert sorted(outcomes)==["confirmed","rejected"]
    with Session(pg_engine) as db:
        assert db.scalar(select(func.count()).select_from(MarketplaceSaleConfirmation).where(MarketplaceSaleConfirmation.listing_id==listing_id))==1
        assert db.scalar(select(func.count()).select_from(FinancialTransaction).where(FinancialTransaction.source_id==listing_id))==1
        assert db.get(Cattle,cattle_id).status==CattleStatus.SOLD
