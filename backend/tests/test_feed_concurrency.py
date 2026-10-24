import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.feed import FeedItem, FeedUnit, StockMovementType
from app.services.feed import FeedValidationError, apply_stock_movement


pytestmark = pytest.mark.integration


def test_concurrent_consumption_cannot_make_inventory_negative(pg_engine):
    user_id, farm_id, item_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "icms_test"
        assert connection.scalar(text("SELECT current_schema()")).startswith("icms_test_")

    with pg_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO users (id, full_name, email, password_hash, is_system_admin, status) "
            "VALUES (:u, 'Feed Concurrent', :email, 'x', false, 'ACTIVE')"
        ), {"u": user_id, "email": f"feed-concurrent-{user_id.hex}@example.com"})
        connection.execute(text(
            "INSERT INTO farms (id, name, owner_id) VALUES (:f, 'Concurrent Feed', :u)"
        ), {"f": farm_id, "u": user_id})
        connection.execute(text(
            "INSERT INTO feed_items "
            "(id, farm_id, name, normalized_name, category, unit, current_quantity, reorder_level, created_by_id) "
            "VALUES (:i, :f, 'Hay', 'hay', 'FORAGE', 'KG', 10, 0, :u)"
        ), {"i": item_id, "f": farm_id, "u": user_id})

    barrier = Barrier(2)

    def consume() -> str:
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            try:
                apply_stock_movement(
                    db,
                    farm_id=farm_id,
                    feed_item_id=item_id,
                    client_request_id=uuid.uuid4(),
                    movement_type=StockMovementType.CONSUMPTION,
                    quantity=Decimal("7"),
                    unit=FeedUnit.KG,
                    actor_id=user_id,
                    reason="Concurrent feeding test",
                    occurred_at=datetime.now(timezone.utc),
                )
                db.commit()
                return "recorded"
            except FeedValidationError:
                db.rollback()
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(consume)
        second = executor.submit(consume)
        outcomes = [first.result(timeout=20), second.result(timeout=20)]

    assert sorted(outcomes) == ["recorded", "rejected"]
    with Session(pg_engine) as db:
        item = db.scalar(select(FeedItem).where(FeedItem.id == item_id))
        assert item.current_quantity == Decimal("3.000")
