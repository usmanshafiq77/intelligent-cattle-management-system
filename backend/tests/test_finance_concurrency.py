import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.finance import (FinanceCategory, FinanceCategoryType, FinancePayment,
    FinanceSourceType, FinanceTransactionStatus, FinancialTransaction, PaymentMethod)
from app.services.finance import FinanceValidationError, record_payment

pytestmark=pytest.mark.integration

def test_concurrent_payments_cannot_exceed_outstanding_balance(pg_engine):
    user_id,farm_id,category_id,transaction_id=[uuid.uuid4() for _ in range(4)]
    with pg_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()"))=="icms_test"
        assert connection.scalar(text("SELECT current_schema()")).startswith("icms_test_")
    with Session(pg_engine) as db:
        db.execute(text("INSERT INTO users (id,full_name,email,password_hash,is_system_admin,status) VALUES (:u,'Finance Concurrent',:e,'x',false,'ACTIVE')"),{"u":user_id,"e":f"finance-concurrent-{user_id.hex}@example.com"})
        db.execute(text("INSERT INTO farms (id,name,owner_id) VALUES (:f,'Concurrent Finance',:u)"),{"f":farm_id,"u":user_id})
        db.add(FinanceCategory(id=category_id,farm_id=farm_id,code="TEST_INCOME",name="Test income",category_type=FinanceCategoryType.INCOME,created_by_id=user_id))
        db.add(FinancialTransaction(id=transaction_id,farm_id=farm_id,client_request_id=uuid.uuid4(),transaction_type=FinanceCategoryType.INCOME,category_id=category_id,amount=Decimal("100.00"),currency="PKR",business_date=date.today(),status=FinanceTransactionStatus.POSTED,description="Concurrency test",source_type=FinanceSourceType.MANUAL,source_id=uuid.uuid4(),created_by_id=user_id,posted_by_id=user_id,posted_at=datetime.now(timezone.utc))); db.commit()
    barrier=Barrier(2)
    def pay():
        with Session(pg_engine) as db:
            row=db.get(FinancialTransaction,transaction_id); barrier.wait(timeout=10)
            try:
                record_payment(db,row,request_id=uuid.uuid4(),amount=Decimal("70"),currency="PKR",paid_at=datetime.now(timezone.utc),method=PaymentMethod.CASH,reference=None,notes=None,actor_id=user_id); db.commit(); return "recorded"
            except FinanceValidationError: db.rollback(); return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes=[f.result(timeout=20) for f in [pool.submit(pay),pool.submit(pay)]]
    assert sorted(outcomes)==["recorded","rejected"]
    with Session(pg_engine) as db: assert sum(db.scalars(select(FinancePayment.amount).where(FinancePayment.transaction_id==transaction_id)))==Decimal("70.00")
    with pg_engine.begin() as connection:
        connection.execute(text("DELETE FROM finance_audit_events WHERE farm_id=:f"),{"f":farm_id}); connection.execute(text("DELETE FROM finance_payments WHERE farm_id=:f"),{"f":farm_id}); connection.execute(text("DELETE FROM financial_transactions WHERE farm_id=:f"),{"f":farm_id}); connection.execute(text("DELETE FROM finance_categories WHERE farm_id=:f"),{"f":farm_id}); connection.execute(text("DELETE FROM farms WHERE id=:f"),{"f":farm_id}); connection.execute(text("DELETE FROM users WHERE id=:u"),{"u":user_id})
