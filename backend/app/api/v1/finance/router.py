from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.finance import *
from app.models.user import User
from app.models.farm import Farm
from app.schemas.finance import *
from app.services.finance import (FinanceValidationError, adjusted_amount, audit,
    available_milk, category, ensure_categories, money, paid_amount, pdf_report,
    period_summary, record_payment, transaction, validate_cattle, xlsx_report)
from app.services.media_storage import MediaStorage, detect_image_content_type, get_media_storage, validate_original_filename
from app.core.config import get_settings

router = APIRouter(prefix="/farms/{farm_id}/finance", tags=["Finance and Resource Management"])


def commit(db, conflict="Duplicate or conflicting finance record"):
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, conflict) from None
    except SQLAlchemyError:
        db.rollback(); raise HTTPException(500, "Finance operation failed") from None


def invalid(error): return HTTPException(422, str(error))


def tx_response(db, row):
    adjusted = adjusted_amount(db, row); paid = paid_amount(db, row); outstanding = money(max(adjusted-paid, Decimal("0")))
    payment_status = "PAID" if outstanding == 0 else ("PARTIAL" if paid else "UNPAID")
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    data.update(adjusted_amount=adjusted, paid_amount=paid, outstanding_amount=outstanding, payment_status=payment_status)
    return TransactionResponse.model_validate(data)


def create_tx(db, farm_id, data, kind, user):
    cat = category(db, farm_id, data.category_id, kind)
    validate_cattle(db, farm_id, data.cattle_id)
    state = FinanceTransactionStatus.POSTED if data.post_now else FinanceTransactionStatus.DRAFT
    now = datetime.now(timezone.utc)
    row = FinancialTransaction(farm_id=farm_id, client_request_id=data.client_request_id,
        transaction_type=kind, category_id=cat.id, amount=money(data.amount), currency=data.currency,
        business_date=data.business_date, due_date=data.due_date, status=state,
        counterparty=data.counterparty, reference=data.reference, description=data.description,
        notes=data.notes, cattle_id=data.cattle_id, source_type=FinanceSourceType.MANUAL,
        source_id=uuid4(), created_by_id=user.id,
        posted_by_id=user.id if data.post_now else None, posted_at=now if data.post_now else None)
    db.add(row); db.flush(); audit(db, farm_id, "transaction", row.id, state.value, f"Created {kind.value.lower()} transaction", user.id)
    commit(db); db.refresh(row); return tx_response(db, row)


@router.get("/categories", response_model=list[CategoryResponse])
def categories(farm_id: UUID, access: FarmAccess = Depends(require_farm_permission(Permission.FINANCE_VIEW)), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_categories(db, farm_id, current_user.id); commit(db)
    return db.scalars(select(FinanceCategory).where(FinanceCategory.farm_id == farm_id, FinanceCategory.is_active.is_(True)).order_by(FinanceCategory.category_type, FinanceCategory.name)).all()


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(farm_id: UUID, data: CategoryCreate, access: FarmAccess = Depends(require_farm_permission(Permission.FINANCE_MANAGE)), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row=FinanceCategory(farm_id=farm_id, code=data.code.upper(), name=data.name, category_type=data.category_type, created_by_id=current_user.id)
    db.add(row); db.flush(); audit(db, farm_id, "category", row.id, "CREATED", "Created finance category", current_user.id); commit(db); db.refresh(row); return row


def list_tx(farm_id, kind, start, end, status_value, category_id, counterparty, payment_status, db):
    q=select(FinancialTransaction).where(FinancialTransaction.farm_id==farm_id, FinancialTransaction.transaction_type==kind)
    if start: q=q.where(FinancialTransaction.business_date>=start)
    if end: q=q.where(FinancialTransaction.business_date<=end)
    if status_value: q=q.where(FinancialTransaction.status==status_value)
    if category_id: q=q.where(FinancialTransaction.category_id==category_id)
    if counterparty: q=q.where(FinancialTransaction.counterparty.ilike(f"%{counterparty.strip()}%"))
    rows=[tx_response(db,row) for row in db.scalars(q.order_by(FinancialTransaction.business_date.desc(),FinancialTransaction.created_at.desc()))]
    return [row for row in rows if not payment_status or row.payment_status==payment_status]


@router.get("/income", response_model=list[TransactionResponse])
def income(farm_id: UUID, start: date|None=None, end: date|None=None, transaction_status: FinanceTransactionStatus|None=None, category_id: UUID|None=None, counterparty: str|None=None, payment_status: str|None=Query(None,pattern="^(UNPAID|PARTIAL|PAID)$"), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    return list_tx(farm_id,FinanceCategoryType.INCOME,start,end,transaction_status,category_id,counterparty,payment_status,db)


@router.post("/income", response_model=TransactionResponse, status_code=201)
def add_income(farm_id: UUID, data: TransactionCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_INCOME_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try: return create_tx(db, farm_id, data, FinanceCategoryType.INCOME, current_user)
    except FinanceValidationError as e: raise invalid(e)


@router.get("/expenses", response_model=list[TransactionResponse])
def expenses(farm_id: UUID, start: date|None=None, end: date|None=None, transaction_status: FinanceTransactionStatus|None=None, category_id: UUID|None=None, supplier: str|None=None, payment_status: str|None=Query(None,pattern="^(UNPAID|PARTIAL|PAID)$"), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    return list_tx(farm_id,FinanceCategoryType.EXPENSE,start,end,transaction_status,category_id,supplier,payment_status,db)


@router.post("/expenses", response_model=TransactionResponse, status_code=201)
def add_expense(farm_id: UUID, data: TransactionCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_EXPENSE_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try: return create_tx(db, farm_id, data, FinanceCategoryType.EXPENSE, current_user)
    except FinanceValidationError as e: raise invalid(e)


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(farm_id: UUID, transaction_id: UUID, data: TransactionUpdate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try:
        row=transaction(db, farm_id, transaction_id, lock=True)
        if row.status != FinanceTransactionStatus.DRAFT: raise FinanceValidationError("Only draft transactions can be edited")
        for key,value in data.model_dump(exclude_unset=True).items(): setattr(row,key,value)
        if data.category_id: category(db, farm_id, data.category_id, row.transaction_type)
        audit(db,farm_id,"transaction",row.id,"UPDATED","Updated draft transaction",current_user.id); commit(db); db.refresh(row); return tx_response(db,row)
    except FinanceValidationError as e: raise invalid(e)


@router.post("/transactions/{transaction_id}/post", response_model=TransactionResponse)
def post_transaction(farm_id: UUID, transaction_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try:
        row=transaction(db,farm_id,transaction_id,lock=True)
        if row.status != FinanceTransactionStatus.DRAFT: raise FinanceValidationError("Only draft transactions can be posted")
        row.status=FinanceTransactionStatus.POSTED; row.posted_at=datetime.now(timezone.utc); row.posted_by_id=current_user.id
        audit(db,farm_id,"transaction",row.id,"POSTED","Posted financial transaction",current_user.id); commit(db); db.refresh(row); return tx_response(db,row)
    except FinanceValidationError as e: raise invalid(e)


@router.post("/transactions/{transaction_id}/adjustments", response_model=TransactionResponse, status_code=201)
def adjust_transaction(farm_id: UUID, transaction_id: UUID, data: AdjustmentCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try:
        row=transaction(db,farm_id,transaction_id,lock=True)
        if row.status != FinanceTransactionStatus.POSTED: raise FinanceValidationError("Only posted transactions can be adjusted")
        if adjusted_amount(db,row)+money(data.amount_delta) < paid_amount(db,row): raise FinanceValidationError("Adjustment cannot reduce the transaction below payments already recorded")
        entry=FinancialAdjustment(farm_id=farm_id,transaction_id=row.id,client_request_id=data.client_request_id,amount_delta=money(data.amount_delta),reason=data.reason,created_by_id=current_user.id)
        db.add(entry); db.flush(); audit(db,farm_id,"transaction",row.id,"ADJUSTED",data.reason,current_user.id); commit(db); return tx_response(db,row)
    except FinanceValidationError as e: raise invalid(e)


@router.get("/payments", response_model=list[PaymentResponse])
def payments(farm_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    return db.scalars(select(FinancePayment).where(FinancePayment.farm_id==farm_id).order_by(FinancePayment.paid_at.desc())).all()


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def add_payment(farm_id: UUID, data: PaymentCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_PAYMENTS_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try:
        row=transaction(db,farm_id,data.transaction_id)
        payment=record_payment(db,row,request_id=data.client_request_id,amount=data.amount,currency=data.currency,paid_at=data.paid_at,method=data.method,reference=data.reference,notes=data.notes,actor_id=current_user.id)
        commit(db); db.refresh(payment); return payment
    except FinanceValidationError as e: raise invalid(e)


async def limited_body(request: Request, maximum: int):
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>maximum: raise HTTPException(413,"Receipt is too large")
        content.extend(chunk)
    return bytes(content)


@router.get("/transactions/{transaction_id}/attachments")
def attachments(farm_id: UUID, transaction_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    transaction(db,farm_id,transaction_id)
    return db.scalars(select(FinanceAttachment).where(FinanceAttachment.farm_id==farm_id,FinanceAttachment.transaction_id==transaction_id,FinanceAttachment.removed_at.is_(None)).order_by(FinanceAttachment.uploaded_at.desc())).all()


@router.post("/transactions/{transaction_id}/attachments", status_code=201)
async def upload_attachment(farm_id: UUID, transaction_id: UUID, request: Request, filename: str=Query(min_length=1,max_length=255), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db), storage: MediaStorage=Depends(get_media_storage)):
    transaction(db,farm_id,transaction_id); maximum=get_settings().CATTLE_MEDIA_MAX_BYTES; content=await limited_body(request,maximum)
    if not content: raise HTTPException(422,"Receipt content is required")
    try: original=validate_original_filename(filename)
    except ValueError as error: raise HTTPException(422,str(error)) from None
    if content.startswith(b"%PDF-"): detected="application/pdf"; extension=".pdf"
    else:
        try: detected=detect_image_content_type(content)
        except ValueError: raise HTTPException(422,"Only valid PDF, JPEG, PNG, and WebP receipts are allowed") from None
        extension={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[detected]
    declared=request.headers.get("content-type","").split(";",1)[0].lower()
    if declared not in {detected,"application/octet-stream"}: raise HTTPException(422,"Declared content type does not match receipt content")
    attachment_id=uuid4(); key=f"finance/{farm_id}/{transaction_id}/{attachment_id}{extension}"; row=FinanceAttachment(id=attachment_id,farm_id=farm_id,transaction_id=transaction_id,storage_key=key,original_filename=original,content_type=detected,size_bytes=len(content),uploaded_by_id=current_user.id)
    try:
        storage.save(key,content); db.add(row); db.flush(); audit(db,farm_id,"attachment",row.id,"UPLOADED","Uploaded financial receipt",current_user.id); db.commit(); db.refresh(row); return row
    except Exception:
        db.rollback(); storage.delete(key); raise HTTPException(500,"Could not store financial receipt") from None


@router.get("/transactions/{transaction_id}/attachments/{attachment_id}/content")
def attachment_content(farm_id: UUID, transaction_id: UUID, attachment_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db), storage: MediaStorage=Depends(get_media_storage)):
    row=db.scalar(select(FinanceAttachment).where(FinanceAttachment.farm_id==farm_id,FinanceAttachment.transaction_id==transaction_id,FinanceAttachment.id==attachment_id,FinanceAttachment.removed_at.is_(None)))
    if not row: raise HTTPException(404,"Receipt not found")
    try: path=storage.resolve(row.storage_key)
    except FileNotFoundError: raise HTTPException(404,"Receipt content not found") from None
    return FileResponse(
        path=path,
        media_type=row.content_type,
        filename=row.original_filename,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/milk-sales")
def milk_sales(farm_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    rows=db.scalars(select(MilkSale).where(MilkSale.farm_id==farm_id).order_by(MilkSale.sale_date.desc())).all(); result=[]
    for row in rows:
        tx=transaction(db,farm_id,row.transaction_id); recognized=adjusted_amount(db,tx); paid=paid_amount(db,tx); data={column.name:getattr(row,column.name) for column in row.__table__.columns}; data.update(currency=tx.currency,paid_amount=paid,outstanding_amount=money(max(recognized-paid,Decimal("0"))),payment_status="PAID" if paid>=recognized else ("PARTIAL" if paid else "UNPAID")); result.append(data)
    return result


@router.post("/milk-sales", status_code=201)
def add_milk_sale(farm_id: UUID, data: MilkSaleCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_SALES_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try:
        db.scalar(select(Farm.id).where(Farm.id==farm_id).with_for_update())
        if data.quantity_liters > available_milk(db,farm_id): raise FinanceValidationError("Milk sale exceeds recorded available production")
        cats=ensure_categories(db,farm_id,current_user.id); total=money(data.quantity_liters*data.price_per_liter); tx_id=uuid4()
        tx=FinancialTransaction(id=tx_id,farm_id=farm_id,client_request_id=data.client_request_id,transaction_type=FinanceCategoryType.INCOME,category_id=cats["MILK_SALES"].id,amount=total,currency=data.currency,business_date=data.sale_date,status=FinanceTransactionStatus.POSTED,counterparty=data.customer,reference=data.invoice_number,description="Milk sale",source_type=FinanceSourceType.MILK_SALE,source_id=tx_id,created_by_id=current_user.id,posted_by_id=current_user.id,posted_at=datetime.now(timezone.utc))
        db.add(tx); db.flush(); sale=MilkSale(farm_id=farm_id,client_request_id=data.client_request_id,transaction_id=tx.id,sale_date=data.sale_date,quantity_liters=data.quantity_liters,price_per_liter=data.price_per_liter,total_amount=total,customer=data.customer,invoice_number=data.invoice_number,notes=data.notes,created_by_id=current_user.id)
        db.add(sale); db.flush(); audit(db,farm_id,"milk_sale",sale.id,"POSTED","Posted milk sale and income",current_user.id); commit(db); db.refresh(sale); return {**{column.name:getattr(sale,column.name) for column in sale.__table__.columns},"currency":tx.currency,"paid_amount":Decimal("0"),"outstanding_amount":total,"payment_status":"UNPAID"}
    except FinanceValidationError as e: raise invalid(e)


@router.get("/cattle-transactions")
def cattle_transactions(farm_id: UUID, cattle_id: UUID|None=None, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    q=select(CattleFinanceTransaction).where(CattleFinanceTransaction.farm_id==farm_id)
    if cattle_id: q=q.where(CattleFinanceTransaction.cattle_id==cattle_id)
    rows=db.scalars(q.order_by(CattleFinanceTransaction.transaction_date.desc())).all(); result=[]
    for row in rows:
        tx=transaction(db,farm_id,row.transaction_id); recognized=adjusted_amount(db,tx); paid=paid_amount(db,tx); data={column.name:getattr(row,column.name) for column in row.__table__.columns}; data.update(amount=recognized,currency=tx.currency,paid_amount=paid,outstanding_amount=money(max(recognized-paid,Decimal("0"))),payment_status="PAID" if paid>=recognized else ("PARTIAL" if paid else "UNPAID")); result.append(data)
    return result


@router.post("/cattle-transactions", status_code=201)
def add_cattle_transaction(farm_id: UUID, data: CattleTransactionCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_SALES_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    try:
        validate_cattle(db,farm_id,data.cattle_id); cats=ensure_categories(db,farm_id,current_user.id)
        income=data.transaction_type==CattleTransactionType.SALE; kind=FinanceCategoryType.INCOME if income else FinanceCategoryType.EXPENSE; key="CATTLE_SALES" if income else "CATTLE_PURCHASES"; source=FinanceSourceType.CATTLE_SALE if income else FinanceSourceType.CATTLE_PURCHASE; tx_id=uuid4()
        tx=FinancialTransaction(id=tx_id,farm_id=farm_id,client_request_id=data.client_request_id,transaction_type=kind,category_id=cats[key].id,amount=money(data.amount),currency=data.currency,business_date=data.transaction_date,status=FinanceTransactionStatus.POSTED,counterparty=data.counterparty,reference=data.reference,description=f"Cattle {data.transaction_type.value.lower()}",notes=data.notes,cattle_id=data.cattle_id,source_type=source,source_id=tx_id,created_by_id=current_user.id,posted_by_id=current_user.id,posted_at=datetime.now(timezone.utc))
        db.add(tx); db.flush(); entry=CattleFinanceTransaction(farm_id=farm_id,client_request_id=data.client_request_id,cattle_id=data.cattle_id,transaction_id=tx.id,transaction_type=data.transaction_type,transaction_date=data.transaction_date,counterparty=data.counterparty,notes=data.notes,created_by_id=current_user.id)
        db.add(entry); db.flush(); audit(db,farm_id,"cattle_transaction",entry.id,"POSTED",f"Posted cattle {data.transaction_type.value.lower()}",current_user.id); commit(db); db.refresh(entry); return entry
    except FinanceValidationError as e: raise invalid(e)


@router.get("/budgets", response_model=list[BudgetResponse])
def budgets(farm_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    return db.scalars(select(FinanceBudget).where(FinanceBudget.farm_id==farm_id).order_by(FinanceBudget.period_start.desc())).all()


@router.post("/budgets", response_model=BudgetResponse, status_code=201)
def add_budget(farm_id: UUID, data: BudgetCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_BUDGETS_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    category(db,farm_id,data.category_id); row=FinanceBudget(farm_id=farm_id,created_by_id=current_user.id,**data.model_dump()); db.add(row); db.flush(); audit(db,farm_id,"budget",row.id,"CREATED","Created budget",current_user.id); commit(db); db.refresh(row); return row


@router.get("/budgets/comparison", response_model=list[BudgetComparisonResponse])
def budget_comparison(farm_id: UUID, start: date, end: date, currency: str="PKR", access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    if start>end: raise HTTPException(422,"start cannot be after end")
    code=currency.upper(); budgets=db.scalars(select(FinanceBudget).where(FinanceBudget.farm_id==farm_id,FinanceBudget.currency==code)).all()
    results=[]
    for budget in budgets:
        period_end=date(budget.period_start.year,12,31) if budget.period==BudgetPeriod.ANNUAL else date(budget.period_start.year,budget.period_start.month,monthrange(budget.period_start.year,budget.period_start.month)[1])
        actual_start=max(start,budget.period_start); actual_end=min(end,period_end)
        if actual_start>actual_end: continue
        transactions=db.scalars(select(FinancialTransaction).where(FinancialTransaction.farm_id==farm_id,FinancialTransaction.category_id==budget.category_id,FinancialTransaction.currency==code,FinancialTransaction.status==FinanceTransactionStatus.POSTED,FinancialTransaction.business_date.between(actual_start,actual_end))).all(); actual=money(sum((adjusted_amount(db,row) for row in transactions),Decimal("0"))); remaining=money(budget.amount-actual)
        results.append({"budget_id":budget.id,"category_id":budget.category_id,"period":budget.period,"period_start":budget.period_start,"period_end":period_end,"budgeted":money(budget.amount),"actual":actual,"remaining":remaining,"over_budget":remaining<0,"currency":code})
    return results


@router.get("/assets", response_model=list[AssetResponse])
def assets(farm_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    return db.scalars(select(FarmAsset).where(FarmAsset.farm_id==farm_id).order_by(FarmAsset.name)).all()


@router.post("/assets", response_model=AssetResponse, status_code=201)
def add_asset(farm_id: UUID, data: AssetCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_ASSETS_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    row=FarmAsset(farm_id=farm_id,created_by_id=current_user.id,**data.model_dump()); db.add(row); db.flush(); audit(db,farm_id,"asset",row.id,"CREATED","Created farm asset",current_user.id); commit(db); db.refresh(row); return row


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
def update_asset(farm_id: UUID, asset_id: UUID, data: AssetUpdate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_ASSETS_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    row=db.scalar(select(FarmAsset).where(FarmAsset.farm_id==farm_id,FarmAsset.id==asset_id).with_for_update())
    if not row: raise HTTPException(404,"Asset not found")
    for key,value in data.model_dump(exclude_unset=True).items(): setattr(row,key,value)
    audit(db,farm_id,"asset",row.id,"UPDATED","Updated farm asset",current_user.id); commit(db); db.refresh(row); return row


@router.post("/assets/{asset_id}/maintenance", status_code=201)
def add_maintenance(farm_id: UUID, asset_id: UUID, data: MaintenanceCreate, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_ASSETS_MANAGE)), current_user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    asset=db.scalar(select(FarmAsset).where(FarmAsset.farm_id==farm_id,FarmAsset.id==asset_id).with_for_update())
    if not asset: raise HTTPException(404,"Asset not found")
    tx=None
    if data.post_expense and data.cost > 0:
        cats=ensure_categories(db,farm_id,current_user.id); tx_id=uuid4(); tx=FinancialTransaction(id=tx_id,farm_id=farm_id,client_request_id=data.client_request_id,transaction_type=FinanceCategoryType.EXPENSE,category_id=cats["MAINTENANCE"].id,amount=money(data.cost),currency=data.currency,business_date=data.performed_on,status=FinanceTransactionStatus.POSTED,counterparty=data.vendor,description=f"Maintenance: {asset.name}",source_type=FinanceSourceType.ASSET_MAINTENANCE,source_id=tx_id,created_by_id=current_user.id,posted_by_id=current_user.id,posted_at=datetime.now(timezone.utc)); db.add(tx); db.flush()
    values=data.model_dump(exclude={"post_expense"}); row=AssetMaintenance(farm_id=farm_id,asset_id=asset_id,financial_transaction_id=tx.id if tx else None,recorded_by_id=current_user.id,**values)
    db.add(row); db.flush(); audit(db,farm_id,"asset_maintenance",row.id,"RECORDED","Recorded asset maintenance",current_user.id); commit(db); db.refresh(row); return row


@router.get("/assets/{asset_id}/maintenance")
def maintenance_history(farm_id: UUID, asset_id: UUID, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    if not db.scalar(select(FarmAsset.id).where(FarmAsset.farm_id==farm_id,FarmAsset.id==asset_id)): raise HTTPException(404,"Asset not found")
    return db.scalars(select(AssetMaintenance).where(AssetMaintenance.farm_id==farm_id,AssetMaintenance.asset_id==asset_id).order_by(AssetMaintenance.performed_on.desc())).all()


@router.get("/reports/summary")
def summary(farm_id: UUID, start: date, end: date, currency: str=Query("PKR",min_length=3,max_length=3), basis: str=Query("ACCRUAL",pattern="^(ACCRUAL|CASH)$"), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_REPORTS_VIEW)), db: Session=Depends(get_db)):
    if start>end: raise HTTPException(422,"start cannot be after end")
    return {"basis":basis,"currency":currency.upper(),"start":start,"end":end,**period_summary(db,farm_id,start,end,basis,currency.upper())}


@router.get("/customers/balances", response_model=list[CustomerBalanceResponse])
def customer_balances(farm_id: UUID, currency: str=Query("PKR",min_length=3,max_length=3), start: date|None=None, end: date|None=None, access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    if start and end and start>end: raise HTTPException(422,"start cannot be after end")
    code=currency.upper(); q=select(MilkSale,FinancialTransaction).join(FinancialTransaction,FinancialTransaction.id==MilkSale.transaction_id).where(MilkSale.farm_id==farm_id,FinancialTransaction.farm_id==farm_id,FinancialTransaction.currency==code,FinancialTransaction.status==FinanceTransactionStatus.POSTED)
    if start: q=q.where(MilkSale.sale_date>=start)
    if end: q=q.where(MilkSale.sale_date<=end)
    balances={}
    for sale,tx in db.execute(q.order_by(MilkSale.sale_date)).all():
        key=sale.customer.casefold(); item=balances.setdefault(key,{"customer":sale.customer,"currency":code,"invoice_count":0,"sales_total":Decimal("0"),"paid_total":Decimal("0"),"outstanding_balance":Decimal("0"),"last_sale_date":sale.sale_date})
        recognized=adjusted_amount(db,tx); paid=paid_amount(db,tx); item["invoice_count"]+=1; item["sales_total"]+=recognized; item["paid_total"]+=paid; item["outstanding_balance"]+=max(recognized-paid,Decimal("0")); item["last_sale_date"]=max(item["last_sale_date"],sale.sale_date)
    return [{**item,"sales_total":money(item["sales_total"]),"paid_total":money(item["paid_total"]),"outstanding_balance":money(item["outstanding_balance"])} for item in sorted(balances.values(),key=lambda row:row["customer"].casefold())]


@router.get("/dashboard")
def dashboard(farm_id: UUID, currency: str="PKR", start: date|None=None, end: date|None=None, basis: str=Query("ACCRUAL",pattern="^(ACCRUAL|CASH)$"), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_VIEW)), db: Session=Depends(get_db)):
    today=date.today(); start=start or date(today.year,today.month,1); end=end or today
    if start>end: raise HTTPException(422,"start cannot be after end")
    code=currency.upper(); result=period_summary(db,farm_id,start,end,basis,code)
    assets_count=db.scalar(select(func.count()).select_from(FarmAsset).where(FarmAsset.farm_id==farm_id,FarmAsset.status==AssetStatus.ACTIVE)) or 0
    transactions=db.scalars(select(FinancialTransaction).where(FinancialTransaction.farm_id==farm_id,FinancialTransaction.status==FinanceTransactionStatus.POSTED,FinancialTransaction.currency==code,FinancialTransaction.business_date.between(start,end)).order_by(FinancialTransaction.business_date)).all()
    categories={row.id:row for row in db.scalars(select(FinanceCategory).where(FinanceCategory.farm_id==farm_id)).all()}; category_totals=defaultdict(Decimal); trend_totals=defaultdict(Decimal); overdue=0
    for tx in transactions:
        value=adjusted_amount(db,tx); category_totals[tx.category_id]+=value; trend_totals[(date(tx.business_date.year,tx.business_date.month,1),tx.transaction_type)]+=value
        if tx.due_date and tx.due_date<today and paid_amount(db,tx)<value: overdue+=1
    breakdown=[{"code":categories[key].code,"name":categories[key].name,"type":categories[key].category_type,"amount":money(value)} for key,value in category_totals.items()]
    by_code={row["code"]:row["amount"] for row in breakdown}; trends=[{"month":month,"type":kind,"amount":money(value)} for (month,kind),value in sorted(trend_totals.items(),key=lambda item:(item[0][0],item[0][1].value))]
    return {"period_start":start,"period_end":end,"basis":basis,"currency":code,"active_assets":assets_count,"potentially_overdue_transactions":overdue,"milk_sales_revenue":by_code.get("MILK_SALES",Decimal("0")),"feed_costs":by_code.get("FEED",Decimal("0")),"veterinary_costs":by_code.get("VETERINARY",Decimal("0"))+by_code.get("MEDICINES",Decimal("0"))+by_code.get("VACCINATIONS",Decimal("0")),"category_breakdown":breakdown,"monthly_trends":trends,**result}


@router.get("/audit")
def audit_log(farm_id: UUID, limit: int=Query(100,ge=1,le=500), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_AUDIT_VIEW)), db: Session=Depends(get_db)):
    return db.scalars(select(FinanceAuditEvent).where(FinanceAuditEvent.farm_id==farm_id).order_by(FinanceAuditEvent.created_at.desc()).limit(limit)).all()


@router.get("/reports/export")
def export_report(farm_id: UUID, start: date, end: date, currency: str="PKR", basis: str=Query("ACCRUAL",pattern="^(ACCRUAL|CASH)$"), report_type: str=Query("operating_result",pattern="^(operating_result|cash_flow|outstanding|milk_sales|feed_expense|category_expense|budget|assets)$"), format: str=Query("xlsx",pattern="^(xlsx|pdf)$"), access: FarmAccess=Depends(require_farm_permission(Permission.FINANCE_REPORTS_VIEW)), db: Session=Depends(get_db)):
    code=currency.upper(); report=period_summary(db,farm_id,start,end,basis,code); headers=["Metric","Amount"]; rows=[]
    if report_type in {"operating_result","cash_flow","outstanding"}:
        wanted={"operating_result":["recognized_income","recognized_expenses","net_operating_result"],"cash_flow":["cash_received","cash_paid"],"outstanding":["outstanding_receivables","outstanding_payables"]}[report_type]
        rows=[[key,str(report[key])] for key in wanted]
    elif report_type=="milk_sales":
        headers=["Date","Invoice","Customer","Litres","Price/litre","Total"]
        sales=db.scalars(select(MilkSale).join(FinancialTransaction,FinancialTransaction.id==MilkSale.transaction_id).where(MilkSale.farm_id==farm_id,MilkSale.sale_date.between(start,end),FinancialTransaction.currency==code).order_by(MilkSale.sale_date)).all(); rows=[[r.sale_date,r.invoice_number,r.customer,r.quantity_liters,r.price_per_liter,r.total_amount] for r in sales]
    elif report_type in {"feed_expense","category_expense"}:
        headers=["Date","Category","Supplier","Reference","Description","Amount"]
        q=select(FinancialTransaction,FinanceCategory).join(FinanceCategory,FinanceCategory.id==FinancialTransaction.category_id).where(FinancialTransaction.farm_id==farm_id,FinancialTransaction.transaction_type==FinanceCategoryType.EXPENSE,FinancialTransaction.status==FinanceTransactionStatus.POSTED,FinancialTransaction.currency==code,FinancialTransaction.business_date.between(start,end))
        if report_type=="feed_expense": q=q.where(FinanceCategory.code=="FEED")
        rows=[[t.business_date,c.name,t.counterparty,t.reference,t.description,adjusted_amount(db,t)] for t,c in db.execute(q.order_by(FinancialTransaction.business_date)).all()]
    elif report_type=="budget":
        headers=["Period","Category ID","Budgeted","Currency"]
        rows=[[r.period_start,r.category_id,r.amount,r.currency] for r in db.scalars(select(FinanceBudget).where(FinanceBudget.farm_id==farm_id,FinanceBudget.currency==code,FinanceBudget.period_start.between(start,end))).all()]
    else:
        headers=["Record","Code","Asset","Category","Status","Condition","Date","Description / vendor","Amount"]
        assets=db.scalars(select(FarmAsset).where(FarmAsset.farm_id==farm_id).order_by(FarmAsset.name)).all(); rows=[]
        for asset in assets:
            rows.append(["Asset",asset.asset_code,asset.name,asset.category,asset.status,asset.condition,asset.purchase_date,"Purchase value",asset.purchase_value or ""])
            maintenance=db.scalars(select(AssetMaintenance).where(AssetMaintenance.farm_id==farm_id,AssetMaintenance.asset_id==asset.id,AssetMaintenance.performed_on.between(start,end)).order_by(AssetMaintenance.performed_on)).all()
            rows.extend([["Maintenance",asset.asset_code,asset.name,asset.category,asset.status,asset.condition,item.performed_on,f"{item.description} / {item.vendor or ''}",item.cost] for item in maintenance])
    if format=="xlsx": return Response(xlsx_report(headers,rows),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=finance-{report_type}.xlsx"})
    lines=[f"ICMS Finance Report - {report_type.replace('_',' ').title()}",f"Period: {start} to {end}",f"Basis: {basis}; Currency: {code}"," | ".join(headers),*[" | ".join(str(value) for value in row) for row in rows]]
    return Response(pdf_report(lines),media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=finance-report.pdf"})
