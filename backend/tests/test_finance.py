import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.cattle import AnimalCategory, AnimalSex, Cattle, Species
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.finance import (FinanceCategoryType, FinanceSourceType,
    FinanceTransactionStatus, FinancialTransaction, MilkSale)
from tests.helpers import authorization_header, create_owned_farm, create_user

pytestmark=pytest.mark.integration

def setup(db, suffix=None):
    suffix=suffix or uuid.uuid4().hex[:8]; owner=create_user(db,email=f"finance-{suffix}@example.com"); farm=create_owned_farm(db,owner=owner,name=f"Finance {suffix}")
    cattle=Cattle(farm_id=farm.id,tag_number=f"C-{suffix}",normalized_tag=f"c-{suffix}",species=Species.CATTLE,sex=AnimalSex.FEMALE,category=AnimalCategory.COW,created_by_id=owner.id); db.add(cattle); db.commit(); return owner,farm,cattle

def categories(client,farm,user):
    response=client.get(f"/api/v1/farms/{farm.id}/finance/categories",headers=authorization_header(user)); assert response.status_code==200,response.text; return {r["code"]:r for r in response.json()}

def test_income_expense_posting_adjustment_payment_and_reports(client,db_session):
    owner,farm,_=setup(db_session); cats=categories(client,farm,owner)
    created=client.post(f"/api/v1/farms/{farm.id}/finance/income",headers=authorization_header(owner),json={"client_request_id":str(uuid.uuid4()),"category_id":cats["OTHER_INCOME"]["id"],"amount":"1000.00","business_date":date.today().isoformat(),"description":"Farm service","post_now":True})
    assert created.status_code==201,created.text; tx=created.json(); assert tx["payment_status"]=="UNPAID"
    payment=client.post(f"/api/v1/farms/{farm.id}/finance/payments",headers=authorization_header(owner),json={"client_request_id":str(uuid.uuid4()),"transaction_id":tx["id"],"amount":"400","currency":"PKR","paid_at":datetime.now(timezone.utc).isoformat(),"method":"BANK_TRANSFER"})
    assert payment.status_code==201,payment.text
    excess=client.post(f"/api/v1/farms/{farm.id}/finance/payments",headers=authorization_header(owner),json={"client_request_id":str(uuid.uuid4()),"transaction_id":tx["id"],"amount":"601","currency":"PKR","paid_at":datetime.now(timezone.utc).isoformat(),"method":"CASH"}); assert excess.status_code==422
    adjusted=client.post(f"/api/v1/farms/{farm.id}/finance/transactions/{tx['id']}/adjustments",headers=authorization_header(owner),json={"client_request_id":str(uuid.uuid4()),"amount_delta":"50","reason":"Approved correction"}); assert adjusted.status_code==201; assert adjusted.json()["adjusted_amount"]=="1050.00"
    report=client.get(f"/api/v1/farms/{farm.id}/finance/reports/summary",headers=authorization_header(owner),params={"start":date.today(),"end":date.today(),"basis":"ACCRUAL","currency":"PKR"}); assert report.status_code==200; assert Decimal(str(report.json()["net_operating_result"]))==Decimal("1050.00")
    cash=client.get(f"/api/v1/farms/{farm.id}/finance/reports/summary",headers=authorization_header(owner),params={"start":date.today(),"end":date.today(),"basis":"CASH","currency":"PKR"}); assert Decimal(str(cash.json()["net_operating_result"]))==Decimal("400.00")

def test_posted_immutable_and_farm_isolation(client,db_session):
    owner,farm,_=setup(db_session); other,other_farm,_=setup(db_session); cats=categories(client,farm,owner)
    created=client.post(f"/api/v1/farms/{farm.id}/finance/expenses",headers=authorization_header(owner),json={"client_request_id":str(uuid.uuid4()),"category_id":cats["UTILITIES"]["id"],"amount":"10","business_date":date.today().isoformat(),"description":"Electricity","post_now":True}); tx=created.json()
    assert client.patch(f"/api/v1/farms/{farm.id}/finance/transactions/{tx['id']}",headers=authorization_header(owner),json={"amount":"12"}).status_code==422
    assert client.patch(f"/api/v1/farms/{other_farm.id}/finance/transactions/{tx['id']}",headers=authorization_header(other),json={"amount":"12"}).status_code==422

def test_worker_denied_financial_data(client,db_session):
    owner,farm,_=setup(db_session); worker=create_user(db_session,email=f"worker-{uuid.uuid4().hex}@example.com"); db_session.add(FarmMember(farm_id=farm.id,user_id=worker.id,role=FarmRole.WORKER,status=MemberStatus.ACTIVE)); db_session.commit()
    assert client.get(f"/api/v1/farms/{farm.id}/finance/dashboard",headers=authorization_header(worker)).status_code==403

def test_cattle_asset_budget_and_exports(client,db_session):
    owner,farm,cattle=setup(db_session); cats=categories(client,farm,owner); headers=authorization_header(owner)
    cattle_tx=client.post(f"/api/v1/farms/{farm.id}/finance/cattle-transactions",headers=headers,json={"client_request_id":str(uuid.uuid4()),"cattle_id":str(cattle.id),"transaction_type":"PURCHASE","transaction_date":date.today().isoformat(),"amount":"50000","counterparty":"Breeder"}); assert cattle_tx.status_code==201,cattle_tx.text
    budget=client.post(f"/api/v1/farms/{farm.id}/finance/budgets",headers=headers,json={"period":"MONTHLY","period_start":date.today().replace(day=1).isoformat(),"category_id":cats["FEED"]["id"],"amount":"20000"}); assert budget.status_code==201,budget.text
    expense=client.post(f"/api/v1/farms/{farm.id}/finance/expenses",headers=headers,json={"client_request_id":str(uuid.uuid4()),"category_id":cats["FEED"]["id"],"amount":"21000","business_date":date.today().isoformat(),"description":"Feed for budget comparison","post_now":True}); assert expense.status_code==201,expense.text
    comparison=client.get(f"/api/v1/farms/{farm.id}/finance/budgets/comparison",headers=headers,params={"start":date.today().replace(day=1),"end":date.today(),"currency":"PKR"}); assert comparison.status_code==200,comparison.text; assert comparison.json()[0]["actual"]=="21000.00"; assert comparison.json()[0]["over_budget"] is True
    asset=client.post(f"/api/v1/farms/{farm.id}/finance/assets",headers=headers,json={"asset_code":"TRACTOR-1","name":"Tractor","category":"Machinery","purchase_value":"100000","currency":"PKR","condition":"GOOD"}); assert asset.status_code==201,asset.text
    for format,media in [("xlsx","spreadsheet"),("pdf","pdf")]:
        response=client.get(f"/api/v1/farms/{farm.id}/finance/reports/export",headers=headers,params={"start":date.today(),"end":date.today(),"format":format}); assert response.status_code==200; assert media in response.headers["content-type"]; assert len(response.content)>100


def test_receipt_download_is_private_and_disables_content_sniffing(client, db_session):
    owner, farm, _ = setup(db_session)
    headers = authorization_header(owner)
    cats = categories(client, farm, owner)
    created = client.post(
        f"/api/v1/farms/{farm.id}/finance/expenses",
        headers=headers,
        json={
            "client_request_id": str(uuid.uuid4()),
            "category_id": cats["SUPPLIES"]["id"],
            "amount": "25.00",
            "business_date": date.today().isoformat(),
            "description": "Receipt header test",
            "post_now": True,
        },
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]
    pdf = b"%PDF-1.4\n%%EOF"
    uploaded = client.post(
        f"/api/v1/farms/{farm.id}/finance/transactions/{transaction_id}/attachments",
        headers={**headers, "Content-Type": "application/pdf"},
        params={"filename": "receipt.pdf"},
        content=pdf,
    )
    assert uploaded.status_code == 201, uploaded.text

    response = client.get(
        f"/api/v1/farms/{farm.id}/finance/transactions/{transaction_id}/attachments/{uploaded.json()['id']}/content",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.content == pdf
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"

def test_feed_purchase_posts_exactly_once(client,db_session):
    owner,farm,_=setup(db_session); headers=authorization_header(owner)
    item=client.post(f"/api/v1/farms/{farm.id}/feed/items",headers=headers,json={"name":"Finance Hay","category":"FORAGE","unit":"KG","reorder_level":"1"}).json(); request_id=uuid.uuid4()
    payload={"client_request_id":str(request_id),"feed_item_id":item["id"],"quantity":"10","unit":"KG","unit_cost":"5","currency":"PKR","occurred_at":datetime.now(timezone.utc).isoformat()}
    first=client.post(f"/api/v1/farms/{farm.id}/feed/stock/purchases",headers=headers,json=payload); assert first.status_code==201,first.text
    second=client.post(f"/api/v1/farms/{farm.id}/feed/stock/purchases",headers=headers,json=payload); assert second.status_code==409
    rows=db_session.scalars(select(FinancialTransaction).where(FinancialTransaction.farm_id==farm.id)).all(); assert len(rows)==1; assert rows[0].amount==Decimal("50.00")

def test_customer_balances_include_partial_payments_and_are_farm_scoped(client,db_session):
    owner,farm,_=setup(db_session); headers=authorization_header(owner); cats=categories(client,farm,owner); tx_id=uuid.uuid4()
    tx=FinancialTransaction(id=tx_id,farm_id=farm.id,client_request_id=uuid.uuid4(),transaction_type=FinanceCategoryType.INCOME,category_id=uuid.UUID(cats["MILK_SALES"]["id"]),amount=Decimal("1000.00"),currency="PKR",business_date=date.today(),status=FinanceTransactionStatus.POSTED,counterparty="Local Dairy",description="Milk sale",source_type=FinanceSourceType.MILK_SALE,source_id=tx_id,created_by_id=owner.id,posted_by_id=owner.id,posted_at=datetime.now(timezone.utc))
    db_session.add(tx); db_session.flush(); db_session.add(MilkSale(farm_id=farm.id,client_request_id=uuid.uuid4(),transaction_id=tx.id,sale_date=date.today(),quantity_liters=Decimal("10"),price_per_liter=Decimal("100"),total_amount=Decimal("1000"),customer="Local Dairy",invoice_number=f"INV-{uuid.uuid4().hex[:8]}",created_by_id=owner.id)); db_session.commit()
    payment=client.post(f"/api/v1/farms/{farm.id}/finance/payments",headers=headers,json={"client_request_id":str(uuid.uuid4()),"transaction_id":str(tx.id),"amount":"250","currency":"PKR","paid_at":datetime.now(timezone.utc).isoformat(),"method":"CASH"}); assert payment.status_code==201,payment.text
    response=client.get(f"/api/v1/farms/{farm.id}/finance/customers/balances",headers=headers); assert response.status_code==200,response.text; assert response.json()==[{"customer":"Local Dairy","currency":"PKR","invoice_count":1,"sales_total":"1000.00","paid_total":"250.00","outstanding_balance":"750.00","last_sale_date":date.today().isoformat()}]
    other,other_farm,_=setup(db_session); assert client.get(f"/api/v1/farms/{other_farm.id}/finance/customers/balances",headers=authorization_header(other)).json()==[]
