import io
import uuid
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cattle import Cattle
from app.models.feed import FeedStockMovement, StockMovementType
from app.models.finance import FinanceAuditEvent, FinanceCategory, FinanceCategoryType, FinancePayment, FinanceSourceType, FinanceTransactionStatus, FinancialAdjustment, FinancialTransaction, MilkSale
from app.models.milk import MilkingSession
from app.services.milk import effective_volume_expression


MONEY = Decimal("0.01")
SYSTEM_CATEGORIES = {
    "MILK_SALES": ("Milk sales", FinanceCategoryType.INCOME), "CATTLE_SALES": ("Cattle sales", FinanceCategoryType.INCOME), "CALF_SALES": ("Calf sales", FinanceCategoryType.INCOME), "MANURE_SALES": ("Manure sales", FinanceCategoryType.INCOME), "FARM_PRODUCTS": ("Other farm products", FinanceCategoryType.INCOME), "OTHER_INCOME": ("Other farm income", FinanceCategoryType.INCOME),
    "FEED": ("Feed purchases", FinanceCategoryType.EXPENSE), "VETERINARY": ("Veterinary services", FinanceCategoryType.EXPENSE), "MEDICINES": ("Medicines", FinanceCategoryType.EXPENSE), "VACCINATIONS": ("Vaccinations", FinanceCategoryType.EXPENSE), "WAGES": ("Worker salaries and wages", FinanceCategoryType.EXPENSE), "TRANSPORT": ("Transport", FinanceCategoryType.EXPENSE), "UTILITIES": ("Utilities", FinanceCategoryType.EXPENSE), "MAINTENANCE": ("Equipment maintenance", FinanceCategoryType.EXPENSE), "SUPPLIES": ("Farm supplies", FinanceCategoryType.EXPENSE), "CATTLE_PURCHASES": ("Cattle purchases", FinanceCategoryType.EXPENSE), "OTHER_EXPENSE": ("Other operating expenses", FinanceCategoryType.EXPENSE),
}


class FinanceValidationError(ValueError): pass


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def ensure_categories(db: Session, farm_id: UUID, actor_id: UUID) -> dict[str, FinanceCategory]:
    existing = {row.code: row for row in db.scalars(select(FinanceCategory).where(FinanceCategory.farm_id == farm_id))}
    for code, (name, kind) in SYSTEM_CATEGORIES.items():
        if code not in existing:
            row = FinanceCategory(farm_id=farm_id, code=code, name=name, category_type=kind, is_system=True, created_by_id=actor_id)
            db.add(row); existing[code] = row
    db.flush()
    return existing


def category(db: Session, farm_id: UUID, category_id: UUID, expected: FinanceCategoryType | None = None) -> FinanceCategory:
    row = db.scalar(select(FinanceCategory).where(FinanceCategory.id == category_id, FinanceCategory.farm_id == farm_id, FinanceCategory.is_active.is_(True)))
    if row is None: raise FinanceValidationError("Financial category was not found in this farm")
    if expected and row.category_type != expected: raise FinanceValidationError("Category type does not match the financial transaction")
    return row


def audit(db: Session, farm_id: UUID, entity_type: str, entity_id: UUID, action: str, summary: str, actor_id: UUID):
    db.add(FinanceAuditEvent(farm_id=farm_id, entity_type=entity_type, entity_id=entity_id, action=action, summary=summary, actor_id=actor_id))


def transaction(db: Session, farm_id: UUID, transaction_id: UUID, lock=False) -> FinancialTransaction:
    q = select(FinancialTransaction).where(FinancialTransaction.id == transaction_id, FinancialTransaction.farm_id == farm_id)
    if lock: q = q.with_for_update()
    row = db.scalar(q)
    if row is None: raise FinanceValidationError("Financial transaction was not found in this farm")
    return row


def adjusted_amount(db: Session, row: FinancialTransaction) -> Decimal:
    delta = db.scalar(select(func.coalesce(func.sum(FinancialAdjustment.amount_delta), 0)).where(FinancialAdjustment.farm_id == row.farm_id, FinancialAdjustment.transaction_id == row.id)) or Decimal("0")
    return money(row.amount + delta)


def paid_amount(db: Session, row: FinancialTransaction) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(FinancePayment.amount), 0)).where(FinancePayment.farm_id == row.farm_id, FinancePayment.transaction_id == row.id)) or Decimal("0")
    return money(total)


def post_feed_purchase(db: Session, movement: FeedStockMovement, actor_id: UUID) -> FinancialTransaction:
    existing = db.scalar(select(FinancialTransaction).where(FinancialTransaction.farm_id == movement.farm_id, FinancialTransaction.source_type == FinanceSourceType.FEED_PURCHASE, FinancialTransaction.source_id == movement.id))
    if existing: return existing
    categories = ensure_categories(db, movement.farm_id, actor_id)
    amount = money(movement.quantity * movement.unit_cost)
    row = FinancialTransaction(farm_id=movement.farm_id, client_request_id=movement.client_request_id, transaction_type=FinanceCategoryType.EXPENSE, category_id=categories["FEED"].id, amount=amount, currency=movement.currency, business_date=movement.occurred_at.date(), status=FinanceTransactionStatus.POSTED, counterparty=movement.supplier, reference=movement.reference, description="Feed purchase", source_type=FinanceSourceType.FEED_PURCHASE, source_id=movement.id, created_by_id=actor_id, posted_by_id=actor_id, posted_at=datetime.now(timezone.utc))
    db.add(row); db.flush(); audit(db, movement.farm_id, "transaction", row.id, "POSTED", "Posted once from authoritative feed purchase source", actor_id)
    return row


def validate_cattle(db: Session, farm_id: UUID, cattle_id: UUID | None):
    if cattle_id and not db.scalar(select(Cattle.id).where(Cattle.id == cattle_id, Cattle.farm_id == farm_id)):
        raise FinanceValidationError("Cattle was not found in this farm")


def available_milk(db: Session, farm_id: UUID) -> Decimal:
    produced = db.scalar(select(func.coalesce(func.sum(effective_volume_expression()), 0)).where(MilkingSession.farm_id == farm_id)) or Decimal("0")
    sold = db.scalar(select(func.coalesce(func.sum(MilkSale.quantity_liters), 0)).where(MilkSale.farm_id == farm_id)) or Decimal("0")
    return produced - sold


def record_payment(db: Session, row: FinancialTransaction, *, request_id: UUID, amount: Decimal, currency: str, paid_at: datetime, method, reference, notes, actor_id: UUID) -> FinancePayment:
    row = transaction(db, row.farm_id, row.id, lock=True)
    if row.status != FinanceTransactionStatus.POSTED: raise FinanceValidationError("Payments require a posted transaction")
    if currency != row.currency: raise FinanceValidationError("Payment currency must match the transaction currency")
    remaining = adjusted_amount(db, row) - paid_amount(db, row)
    amount = money(amount)
    if amount <= 0 or amount > remaining: raise FinanceValidationError("Payment exceeds the outstanding balance")
    payment = FinancePayment(farm_id=row.farm_id, transaction_id=row.id, client_request_id=request_id, amount=amount, currency=currency, paid_at=paid_at, method=method, reference=reference, notes=notes, recorded_by_id=actor_id)
    db.add(payment); db.flush(); audit(db, row.farm_id, "payment", payment.id, "RECORDED", f"Recorded {currency} {amount} payment", actor_id)
    return payment


def period_summary(db: Session, farm_id: UUID, start: date, end: date, basis: str, currency: str):
    rows = db.scalars(select(FinancialTransaction).where(FinancialTransaction.farm_id == farm_id, FinancialTransaction.status == FinanceTransactionStatus.POSTED, FinancialTransaction.business_date.between(start, end), FinancialTransaction.currency == currency)).all()
    income = expense = cash_in = cash_out = receivable = payable = Decimal("0")
    by_category = {}
    for row in rows:
        recognized = adjusted_amount(db, row); paid = paid_amount(db, row); amount = paid if basis == "CASH" else recognized
        key = str(row.category_id); by_category[key] = money(by_category.get(key, Decimal("0")) + amount)
        if row.transaction_type == FinanceCategoryType.INCOME:
            income += amount; cash_in += paid; receivable += max(recognized - paid, Decimal("0"))
        else:
            expense += amount; cash_out += paid; payable += max(recognized - paid, Decimal("0"))
    return {"recognized_income": money(income), "recognized_expenses": money(expense), "net_operating_result": money(income-expense), "cash_received": money(cash_in), "cash_paid": money(cash_out), "outstanding_receivables": money(receivable), "outstanding_payables": money(payable), "category_totals": by_category}


def safe_cell(value) -> str:
    text = str(value if value is not None else "")
    if text.startswith(("=", "+", "-", "@")): text = "'" + text
    return text


def xlsx_report(headers, rows) -> bytes:
    def cell(ref, value): return f'<c r="{ref}" t="inlineStr"><is><t>{escape(safe_cell(value))}</t></is></c>'
    xml_rows=[]
    for ri, values in enumerate([headers, *rows], 1):
        cells=[]
        for ci, value in enumerate(values, 1):
            n=ci; letters=""
            while n: n, rem=divmod(n-1,26); letters=chr(65+rem)+letters
            cells.append(cell(f"{letters}{ri}", value))
        xml_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
    sheet='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(xml_rows)+'</sheetData></worksheet>'
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Finance Report" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()


def pdf_report(lines) -> bytes:
    def pdf_escape(value) -> str:
        return safe_cell(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content="BT /F1 10 Tf 50 790 Td 14 TL " + " ".join(f"({pdf_escape(line)}) Tj T*" for line in lines[:50]) + " ET"
    objects=["<< /Type /Catalog /Pages 2 0 R >>","<< /Type /Pages /Kids [3 0 R] /Count 1 >>","<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",f"<< /Length {len(content.encode())} >>\nstream\n{content}\nendstream","<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out=bytearray(b"%PDF-1.4\n"); offsets=[0]
    for i,obj in enumerate(objects,1): offsets.append(len(out)); out.extend(f"{i} 0 obj\n{obj}\nendobj\n".encode())
    xref=len(out); out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]: out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()); return bytes(out)
