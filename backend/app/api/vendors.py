from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Vendor
router = APIRouter(prefix="/vendors", tags=["vendors"])

@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    return [{"id": r.id, "market_day_id": r.market_day_id, "name": r.name,
             "stall_width_m": r.stall_width_m, "priority": r.priority}
            for r in db.scalars(select(Vendor).order_by(Vendor.priority, Vendor.id)).all()]
