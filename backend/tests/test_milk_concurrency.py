
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.cattle import Cattle
from app.models.milk import MilkLactation
from app.services.milk import MilkValidationError, validate_lactation_dates


pytestmark = pytest.mark.integration


def test_concurrent_lactation_creation_is_serialized(pg_engine):
    """
    Two independent PostgreSQL transactions attempt to create
    overlapping lactations for the same cow.

    Expected:
    - One creation succeeds.
    - The other is rejected after acquiring the cattle lock.
    - Only one lactation exists.
    """

    user_id = uuid.uuid4()
    farm_id = uuid.uuid4()
    cattle_id = uuid.uuid4()

    # Confirm database and disposable schema.
    with pg_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT current_database()")
        ) == "icms_test"

        schema_name = connection.scalar(
            text("SELECT current_schema()")
        )

        assert schema_name.startswith("icms_test_")

    # Create committed setup data so that independent
    # PostgreSQL connections can see it.
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, full_name, email, password_hash, "
                "is_system_admin, status) "
                "VALUES "
                "(:id, 'Concurrency Test Owner', :email, "
                "'test-only', false, 'ACTIVE')"
            ),
            {
                "id": user_id,
                "email": f"milk-concurrency-{user_id.hex}@example.com",
            },
        )

        connection.execute(
            text(
                "INSERT INTO farms (id, name, owner_id) "
                "VALUES (:id, 'Concurrency Test Farm', :owner_id)"
            ),
            {
                "id": farm_id,
                "owner_id": user_id,
            },
        )

        connection.execute(
            text(
                "INSERT INTO cattle "
                "(id, farm_id, tag_number, normalized_tag, "
                "species, sex, category, created_by_id) "
                "VALUES "
                "(:id, :farm_id, :tag, :normalized_tag, "
                "'CATTLE', 'FEMALE', 'COW', :user_id)"
            ),
            {
                "id": cattle_id,
                "farm_id": farm_id,
                "tag": f"CON-{cattle_id.hex[:12]}",
                "normalized_tag": f"con-{cattle_id.hex[:12]}",
                "user_id": user_id,
            },
        )

    barrier = Barrier(2)

    def create_lactation_concurrently(sequence_number: int) -> str:
        # Each worker creates its own SQLAlchemy Session
        # and uses its own PostgreSQL connection.
        with Session(pg_engine) as db:
            # Start both workers close together.
            barrier.wait(timeout=10)

            try:
                # Same lock convention used by the API.
                locked_cattle = db.scalar(
                    select(Cattle.id)
                    .where(
                        Cattle.id == cattle_id,
                        Cattle.farm_id == farm_id,
                    )
                    .with_for_update()
                )

                assert locked_cattle == cattle_id

                # Check overlap while holding the lock.
                validate_lactation_dates(
                    db,
                    farm_id=farm_id,
                    cattle_id=cattle_id,
                    start_date=date(2026, 1, 1),
                )

                record = MilkLactation(
                    farm_id=farm_id,
                    cattle_id=cattle_id,
                    sequence_number=sequence_number,
                    start_date=date(2026, 1, 1),
                    created_by_id=user_id,
                )

                db.add(record)
                db.commit()

                return "created"

            except MilkValidationError:
                db.rollback()
                return "overlap_rejected"

    # Execute both transactions in parallel.
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(create_lactation_concurrently, 1)
        second = executor.submit(create_lactation_concurrently, 2)

        results = [
            first.result(timeout=20),
            second.result(timeout=20),
        ]

    assert sorted(results) == [
        "created",
        "overlap_rejected",
    ]

    # Verify only one lactation was persisted.
    with Session(pg_engine) as db:
        records = list(
            db.scalars(
                select(MilkLactation).where(
                    MilkLactation.farm_id == farm_id,
                    MilkLactation.cattle_id == cattle_id,
                )
            )
        )

        assert len(records) == 1
        assert records[0].status.value == "ACTIVE"
