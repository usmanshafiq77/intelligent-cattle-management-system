import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.breeding import ParentRole, ParentageStatus
from app.models.cattle import Cattle
from app.schemas.breeding import ParentageCreate
from app.services.breeding import BreedingValidationError, assign_parentage


pytestmark = pytest.mark.integration


def test_concurrent_conflicting_parentage_does_not_silently_overwrite(pg_engine):
    user, farm, child, first_dam, second_dam = [uuid.uuid4() for _ in range(5)]
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "icms_test"
        assert connection.scalar(text("SELECT current_schema()")).startswith("icms_test_")
    with pg_engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, full_name, email, password_hash, is_system_admin, status) VALUES (:u, 'Concurrent', :e, 'x', false, 'ACTIVE')"), {"u": user, "e": f"breed-concurrent-{user.hex}@example.com"})
        connection.execute(text("INSERT INTO farms (id, name, owner_id) VALUES (:f, 'Concurrent Pedigree', :u)"), {"f": farm, "u": user})
        for cattle_id, tag in [(child, "CHILD"), (first_dam, "DAM-1"), (second_dam, "DAM-2")]:
            connection.execute(text("INSERT INTO cattle (id, farm_id, tag_number, normalized_tag, species, sex, category, created_by_id) VALUES (:c, :f, :t, :n, 'CATTLE', 'FEMALE', :category, :u)"), {"c": cattle_id, "f": farm, "t": tag, "n": tag.lower(), "category": "CALF" if cattle_id == child else "COW", "u": user})
    barrier = Barrier(2)
    def set_dam(parent_id):
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            try:
                assign_parentage(db, farm_id=farm, data=ParentageCreate(client_request_id=uuid.uuid4(), child_id=child, parent_id=parent_id, parent_role=ParentRole.DAM, status=ParentageStatus.REPORTED), actor_id=user)
                db.commit(); return "recorded"
            except BreedingValidationError:
                db.rollback(); return "rejected"
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result(timeout=20) for future in [executor.submit(set_dam, first_dam), executor.submit(set_dam, second_dam)]]
    assert sorted(outcomes) == ["recorded", "rejected"]
    with Session(pg_engine) as db:
        assert db.scalar(select(Cattle.mother_id).where(Cattle.id == child)) in {first_dam, second_dam}
    with pg_engine.begin() as connection:
        connection.execute(text("DELETE FROM breeding_audit_events WHERE farm_id = :f"), {"f": farm})
        connection.execute(text("DELETE FROM parentage_verifications WHERE farm_id = :f"), {"f": farm})
        connection.execute(text("DELETE FROM cattle WHERE farm_id = :f"), {"f": farm})
        connection.execute(text("DELETE FROM farms WHERE id = :f"), {"f": farm})
        connection.execute(text("DELETE FROM users WHERE id = :u"), {"u": user})
